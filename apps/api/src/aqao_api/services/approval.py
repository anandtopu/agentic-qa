"""ApprovalService — Story 2.1.1.

Owns the lifecycle of every row in ``approval_requests`` (PRD §9.10):

    pending -> approved | rejected | expired | cancelled

Every transition is mirrored into the audit log so the reviewer who
clicked Approve is recoverable months later. The service is the single
write path for the table — workflow steps that need to pause for human
sign-off call ``request()`` here, then resume on the resulting row's
state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    ApprovalEventType,
    ApprovalRequest,
    ApprovalState,
)
from aqao_api.notifications import (
    ApprovalNotification,
    LogNotifier,
    Notifier,
    NotifierError,
)
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import (
    InvalidStateError,
    ResourceNotFoundError,
)

DEFAULT_APPROVAL_TTL = timedelta(hours=24)


class ApprovalService:
    """Single write path for human approval gates."""

    def __init__(
        self,
        session: Session,
        *,
        default_ttl: timedelta = DEFAULT_APPROVAL_TTL,
        notifier: Notifier | None = None,
    ) -> None:
        self._session = session
        self._audit = AuditService(session)
        self._default_ttl = default_ttl
        self._notifier = notifier or LogNotifier()
        self._log = structlog.get_logger("aqao_api.services.approval")

    # ------------------------------------------------------------------ create

    def request(
        self,
        *,
        event_type: ApprovalEventType | str,
        subject: str,
        context: RequestContext,
        workspace_id: UUID | None = None,
        test_run_id: UUID | None = None,
        reason: str | None = None,
        gate_context: Mapping[str, Any] | None = None,
        ttl: timedelta | None = None,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        """Create a fresh ``pending`` approval request."""
        event_value = (
            event_type.value if isinstance(event_type, ApprovalEventType) else str(event_type)
        )
        # Normalise so callers can pass the policy enum directly.
        ApprovalEventType(event_value)  # raises ValueError on unknown gates

        moment = now or datetime.now(UTC)
        expires_at = moment + (ttl if ttl is not None else self._default_ttl)
        record = ApprovalRequest(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            test_run_id=test_run_id,
            event_type=event_value,
            state=ApprovalState.PENDING.value,
            subject=subject,
            reason=reason,
            context=dict(gate_context or {}),
            requested_by=context.user_id,
            expires_at=expires_at,
        )
        self._session.add(record)
        self._session.flush()

        self._audit.record(
            context=context,
            action="approval.request",
            resource_type="approval_request",
            resource_id=record.id,
            payload={
                "event_type": event_value,
                "subject": subject,
                "expires_at": expires_at.isoformat(),
            },
        )
        self._notify(record, context=context, on_decide=False)
        return record

    # ------------------------------------------------------------------ read

    def get(self, *, request_id: UUID) -> ApprovalRequest:
        record = self._session.get(ApprovalRequest, request_id)
        if record is None:
            raise ResourceNotFoundError("approval_request", request_id)
        return record

    def list_requests(
        self,
        *,
        states: Sequence[ApprovalState | str] | None = None,
        workspace_id: UUID | None = None,
        event_type: ApprovalEventType | str | None = None,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        clauses: list[Any] = []
        if states:
            wanted = [s.value if isinstance(s, ApprovalState) else s for s in states]
            clauses.append(ApprovalRequest.state.in_(wanted))
        if workspace_id is not None:
            clauses.append(ApprovalRequest.workspace_id == workspace_id)
        if event_type is not None:
            event_value = (
                event_type.value if isinstance(event_type, ApprovalEventType) else event_type
            )
            clauses.append(ApprovalRequest.event_type == event_value)

        stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).limit(limit)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        return list(self._session.scalars(stmt).all())

    # ------------------------------------------------------------------ decide

    def approve(
        self,
        *,
        request_id: UUID,
        context: RequestContext,
        comment: str | None = None,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        return self._decide(
            request_id=request_id,
            target=ApprovalState.APPROVED,
            context=context,
            comment=comment,
            now=now,
        )

    def reject(
        self,
        *,
        request_id: UUID,
        context: RequestContext,
        comment: str | None = None,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        return self._decide(
            request_id=request_id,
            target=ApprovalState.REJECTED,
            context=context,
            comment=comment,
            now=now,
        )

    def cancel(
        self,
        *,
        request_id: UUID,
        context: RequestContext,
        comment: str | None = None,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        return self._decide(
            request_id=request_id,
            target=ApprovalState.CANCELLED,
            context=context,
            comment=comment,
            now=now,
        )

    # ------------------------------------------------------------------ expire

    def expire_due(
        self,
        *,
        context: RequestContext,
        now: datetime | None = None,
        limit: int = 200,
    ) -> list[ApprovalRequest]:
        """Mark every overdue ``pending`` row as ``expired``.

        Intended to run on a scheduled job — caller picks the cadence.
        Returns the rows that were transitioned so the caller can fan
        out notifications.
        """
        moment = now or datetime.now(UTC)
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.state == ApprovalState.PENDING.value,
                ApprovalRequest.expires_at.is_not(None),
                ApprovalRequest.expires_at <= moment,
            )
            .order_by(ApprovalRequest.expires_at.asc())
            .limit(limit)
        )
        rows = list(self._session.scalars(stmt).all())
        for row in rows:
            row.state = ApprovalState.EXPIRED.value
            row.decided_at = moment
            self._audit.record(
                context=context,
                action="approval.expire",
                resource_type="approval_request",
                resource_id=row.id,
                payload={"event_type": row.event_type},
            )
        if rows:
            self._session.flush()
        return rows

    # ------------------------------------------------------------------ helpers

    def _decide(
        self,
        *,
        request_id: UUID,
        target: ApprovalState,
        context: RequestContext,
        comment: str | None,
        now: datetime | None,
    ) -> ApprovalRequest:
        record = self.get(request_id=request_id)
        if record.state != ApprovalState.PENDING.value:
            raise InvalidStateError("approval_request", record.state, target.value)

        moment = now or datetime.now(UTC)
        if (
            target is ApprovalState.APPROVED
            and record.expires_at is not None
            and moment >= record.expires_at
        ):
            # Auto-expire stale rows on first decision attempt rather
            # than letting a late approval slip through.
            record.state = ApprovalState.EXPIRED.value
            record.decided_at = moment
            self._audit.record(
                context=context,
                action="approval.expire",
                resource_type="approval_request",
                resource_id=record.id,
                payload={"event_type": record.event_type, "via": "decision"},
            )
            self._session.flush()
            raise InvalidStateError("approval_request", ApprovalState.EXPIRED.value, target.value)

        record.state = target.value
        record.decided_by = context.user_id
        record.decision_comment = comment
        record.decided_at = moment
        self._session.flush()

        self._audit.record(
            context=context,
            action=f"approval.{target.value}",
            resource_type="approval_request",
            resource_id=record.id,
            payload={
                "event_type": record.event_type,
                "comment": comment,
            },
        )
        self._notify(record, context=context, on_decide=True)
        return record

    def _notify(
        self,
        record: ApprovalRequest,
        *,
        context: RequestContext,
        on_decide: bool,
    ) -> None:
        """Fan a notification out — never fatal if the transport
        falls over. We log + swallow so a Slack outage cannot block
        a destructive-SQL approval being recorded."""
        payload = ApprovalNotification(
            request_id=record.id,
            tenant_id=record.tenant_id,
            workspace_id=record.workspace_id,
            event_type=record.event_type,
            state=record.state,
            subject=record.subject,
            reason=record.reason,
            requested_by=record.requested_by,
            decided_by=record.decided_by,
            expires_at=record.expires_at,
            correlation_id=context.correlation_id,
            extra=dict(record.context or {}),
        )
        try:
            if on_decide:
                self._notifier.notify_decided(payload)
            else:
                self._notifier.notify_requested(payload)
        except NotifierError as exc:
            self._log.warning(
                "approval.notify_failed",
                request_id=str(record.id),
                error=str(exc),
            )


__all__ = [
    "DEFAULT_APPROVAL_TTL",
    "ApprovalService",
]
