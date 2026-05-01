"""ModelLifecycleService — Story 6.2.1.

Tracks new Claude / OpenAI / Gemini releases through the platform's
go/no-go gate. The service is the single write path for the
``model_registry`` table:

* :meth:`register` — record a newly released model. Idempotent on
  ``(provider, model_id)`` per tenant.
* :meth:`attach_scorecard` — link a candidate to the eval scorecard
  that backs the eventual decision.
* :meth:`record_decision` — go/no-go transition. ``go`` pins the
  model; ``no_go`` rejects it. Either path stamps decision metadata
  and emits an audit event.
* :meth:`deprecate` — schedule sunset on a previously-pinned model.
* :meth:`awaiting_decision` — list candidates whose decision is
  overdue per the configurable SLA (default 14 days, mirroring the
  Epic 6.2 acceptance criterion).

State transitions are deliberately tight:

    candidate ─ decision=go    ─▶ pinned ── deprecate ──▶ deprecated
              ─ decision=no_go ─▶ rejected

Any other transition raises :class:`InvalidLifecycleTransitionError`.
Pinning while another model in the same family is already pinned is
allowed at this layer — A/B traffic split is the prompt registry's
concern (Story 3.4.2), not this one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    ModelDecision,
    ModelLifecycleStatus,
    ModelRegistryEntry,
)
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError, ServiceError

DEFAULT_DECISION_SLA = timedelta(days=14)


class InvalidLifecycleTransitionError(ServiceError):
    """Raised when a decision/deprecation is attempted from an incompatible status."""

    def __init__(
        self,
        *,
        entry_id: UUID,
        current_status: str,
        attempted: str,
    ) -> None:
        super().__init__(
            f"model_registry {entry_id} cannot {attempted!r} from status {current_status!r}"
        )
        self.entry_id = entry_id
        self.current_status = current_status
        self.attempted = attempted


@dataclass(slots=True, frozen=True)
class AwaitingDecisionRow:
    entry: ModelRegistryEntry
    age_days: int
    sla_breached: bool


class ModelLifecycleService:
    """Single write + read point for model_registry."""

    def __init__(
        self,
        session: Session,
        *,
        audit: AuditService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(UTC))

    # -------------------------------------------------------- writes

    def register(
        self,
        *,
        context: RequestContext,
        provider: str,
        model_id: str,
        family: str | None,
        released_at: datetime,
    ) -> ModelRegistryEntry:
        """Idempotent: re-registering an existing (tenant, provider, model)
        returns the row unchanged — the registry remembers, callers don't
        need to."""
        existing = self._find(
            tenant_id=context.tenant_id, provider=provider, model_id=model_id
        )
        if existing is not None:
            return existing
        row = ModelRegistryEntry(
            tenant_id=context.tenant_id,
            provider=provider,
            model_id=model_id,
            family=family,
            released_at=released_at,
            status=ModelLifecycleStatus.CANDIDATE.value,
        )
        self._session.add(row)
        self._session.flush()
        self._audit_event(
            context,
            action="model_registry.registered",
            entry=row,
            extra={"family": family, "released_at": released_at.isoformat()},
        )
        return row

    def attach_scorecard(
        self,
        *,
        context: RequestContext,
        entry_id: UUID,
        eval_scorecard_id: str,
        eval_scorecard_path: str | None,
    ) -> ModelRegistryEntry:
        row = self._require(entry_id)
        row.eval_scorecard_id = eval_scorecard_id
        row.eval_scorecard_path = eval_scorecard_path
        self._session.flush()
        self._audit_event(
            context,
            action="model_registry.scorecard_attached",
            entry=row,
            extra={"eval_scorecard_id": eval_scorecard_id},
        )
        return row

    def record_decision(
        self,
        *,
        context: RequestContext,
        entry_id: UUID,
        decision: ModelDecision,
        rationale: str,
    ) -> ModelRegistryEntry:
        row = self._require(entry_id)
        if row.status != ModelLifecycleStatus.CANDIDATE.value:
            raise InvalidLifecycleTransitionError(
                entry_id=entry_id,
                current_status=row.status,
                attempted=f"decide:{decision.value}",
            )
        row.decision = decision.value
        row.decision_rationale = rationale
        row.decision_at = self._clock()
        row.decided_by_user_id = context.user_id
        row.status = (
            ModelLifecycleStatus.PINNED.value
            if decision is ModelDecision.GO
            else ModelLifecycleStatus.REJECTED.value
        )
        self._session.flush()
        self._audit_event(
            context,
            action="model_registry.decision_recorded",
            entry=row,
            extra={"decision": decision.value, "rationale_length": len(rationale)},
        )
        return row

    def deprecate(
        self,
        *,
        context: RequestContext,
        entry_id: UUID,
        deprecation_at: datetime,
    ) -> ModelRegistryEntry:
        row = self._require(entry_id)
        if row.status != ModelLifecycleStatus.PINNED.value:
            raise InvalidLifecycleTransitionError(
                entry_id=entry_id,
                current_status=row.status,
                attempted="deprecate",
            )
        row.deprecation_at = deprecation_at
        row.status = ModelLifecycleStatus.DEPRECATED.value
        self._session.flush()
        self._audit_event(
            context,
            action="model_registry.deprecated",
            entry=row,
            extra={"deprecation_at": deprecation_at.isoformat()},
        )
        return row

    # -------------------------------------------------------- reads

    def get(self, entry_id: UUID) -> ModelRegistryEntry:
        return self._require(entry_id)

    def list_entries(
        self,
        *,
        tenant_id: UUID,
        status: ModelLifecycleStatus | None = None,
    ) -> list[ModelRegistryEntry]:
        stmt = select(ModelRegistryEntry).where(
            ModelRegistryEntry.tenant_id == tenant_id
        )
        if status is not None:
            stmt = stmt.where(ModelRegistryEntry.status == status.value)
        stmt = stmt.order_by(ModelRegistryEntry.released_at.desc())
        return list(self._session.scalars(stmt).all())

    def awaiting_decision(
        self,
        *,
        tenant_id: UUID,
        sla: timedelta = DEFAULT_DECISION_SLA,
        now: datetime | None = None,
    ) -> list[AwaitingDecisionRow]:
        """Candidates whose go/no-go is still outstanding.

        Order: oldest-released first, so an operator clears the most
        overdue decisions before the fresher ones. Each row carries
        ``age_days`` and the boolean ``sla_breached`` flag — the alert
        kind ``PROVIDER_DECISION_OVERDUE`` (Phase-4 incident routing)
        watches the breach count to decide when to page.
        """
        moment = now or self._clock()
        stmt = (
            select(ModelRegistryEntry)
            .where(
                ModelRegistryEntry.tenant_id == tenant_id,
                ModelRegistryEntry.status == ModelLifecycleStatus.CANDIDATE.value,
                ModelRegistryEntry.decision.is_(None),
            )
            .order_by(ModelRegistryEntry.released_at.asc())
        )
        rows = self._session.scalars(stmt).all()
        out: list[AwaitingDecisionRow] = []
        for row in rows:
            age = moment - row.released_at
            age_days = max(0, int(age.total_seconds() // 86400))
            out.append(
                AwaitingDecisionRow(
                    entry=row,
                    age_days=age_days,
                    sla_breached=age >= sla,
                )
            )
        return out

    # -------------------------------------------------------- helpers

    def _find(
        self, *, tenant_id: UUID, provider: str, model_id: str
    ) -> ModelRegistryEntry | None:
        stmt = select(ModelRegistryEntry).where(
            ModelRegistryEntry.tenant_id == tenant_id,
            ModelRegistryEntry.provider == provider,
            ModelRegistryEntry.model_id == model_id,
        )
        return self._session.scalars(stmt).first()

    def _require(self, entry_id: UUID) -> ModelRegistryEntry:
        row = self._session.get(ModelRegistryEntry, entry_id)
        if row is None:
            raise ResourceNotFoundError("model_registry", entry_id)
        return row

    def _audit_event(
        self,
        context: RequestContext,
        *,
        action: str,
        entry: ModelRegistryEntry,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._audit is None:
            return
        payload: dict[str, object] = {
            "provider": entry.provider,
            "model_id": entry.model_id,
            "status": entry.status,
        }
        if extra is not None:
            payload.update(extra)
        self._audit.record(
            context=context,
            action=action,
            resource_type="model_registry",
            resource_id=entry.id,
            payload=payload,
        )


__all__ = [
    "DEFAULT_DECISION_SLA",
    "AwaitingDecisionRow",
    "InvalidLifecycleTransitionError",
    "ModelLifecycleService",
]
