"""ExternalIssueService — Stories 3.2.1 / 3.2.2.

Single write-path for ``external_issues``. Coordinates:

* dedup: don't open a second issue for the same ``(workspace, signal,
  provider)`` within the configured window (PRD AC: 24 h);
* create: invoke the provider's :class:`ExternalIssueClient` and
  persist the link, audit-logged;
* sync: when an upstream webhook fires, map the provider-native
  status into :class:`IssueStatus` and update the link.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    ExternalIssue,
    IssueProvider,
    IssueStatus,
)
from aqao_api.integrations.external_issues import (
    ExternalIssueClient,
    IssueDraft,
)
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError

DEFAULT_DEDUP_WINDOW = timedelta(hours=24)


_PROVIDER_STATUS_MAP: Mapping[str, Mapping[str, IssueStatus]] = {
    IssueProvider.JIRA.value: {
        "new": IssueStatus.OPEN,
        "indeterminate": IssueStatus.IN_PROGRESS,
        "done": IssueStatus.CLOSED,
        "closed": IssueStatus.CLOSED,
        "resolved": IssueStatus.RESOLVED,
    },
    IssueProvider.GITHUB.value: {
        "open": IssueStatus.OPEN,
        "closed": IssueStatus.CLOSED,
    },
}


@dataclass(slots=True, frozen=True)
class CreateOrReuseResult:
    """Outcome of :meth:`ExternalIssueService.create_or_reuse`."""

    link: ExternalIssue
    deduped: bool


class ExternalIssueService:
    """Single write-path for ``external_issues``."""

    def __init__(
        self,
        session: Session,
        *,
        dedup_window: timedelta = DEFAULT_DEDUP_WINDOW,
    ) -> None:
        self._session = session
        self._audit = AuditService(session)
        self._dedup_window = dedup_window

    # ------------------------------------------------------------ create

    def create_or_reuse(
        self,
        *,
        client: ExternalIssueClient,
        workspace_id: UUID,
        signal_id: str,
        draft: IssueDraft,
        context: RequestContext,
        classification_id: UUID | None = None,
        now: datetime | None = None,
    ) -> CreateOrReuseResult:
        """File an issue if no recent link exists; otherwise return
        the existing link with ``deduped=True``."""
        moment = now or datetime.now(UTC)
        existing = self._lookup_recent(
            workspace_id=workspace_id,
            signal_id=signal_id,
            provider=client.provider,
            since=moment - self._dedup_window,
        )
        if existing is not None:
            self._audit.record(
                context=context,
                action="external_issue.deduped",
                resource_type="external_issue",
                resource_id=existing.id,
                payload={
                    "provider": existing.provider,
                    "issue_key": existing.issue_key,
                    "signal_id": signal_id,
                },
            )
            return CreateOrReuseResult(link=existing, deduped=True)

        created = client.create(draft)
        link = ExternalIssue(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            classification_id=classification_id,
            signal_id=signal_id,
            provider=client.provider,
            project_key=draft.project_key,
            issue_key=created.issue_key,
            issue_url=created.issue_url,
            status=IssueStatus.OPEN.value,
            title=draft.title,
            opened_by=context.user_id,
            opened_at=moment,
        )
        self._session.add(link)
        self._session.flush()

        self._audit.record(
            context=context,
            action="external_issue.create",
            resource_type="external_issue",
            resource_id=link.id,
            payload={
                "provider": client.provider,
                "project_key": draft.project_key,
                "issue_key": created.issue_key,
                "issue_url": created.issue_url,
                "signal_id": signal_id,
            },
        )
        return CreateOrReuseResult(link=link, deduped=False)

    # ------------------------------------------------------------ sync

    def sync_from_provider(
        self,
        *,
        provider: str,
        issue_key: str,
        provider_status: str,
        closed_at: datetime | None,
        raw: dict[str, Any] | None = None,
        context: RequestContext,
    ) -> ExternalIssue:
        """Map the provider's native status into :class:`IssueStatus`
        and write it through. Used by the webhook handler.

        Raises :class:`ResourceNotFoundError` if the issue isn't
        linked — the webhook caller should swallow that case so we
        never crash on traffic we don't own.
        """
        link = self._lookup_by_provider_key(provider=provider, issue_key=issue_key)
        if link is None:
            raise ResourceNotFoundError("external_issue", (provider, issue_key))
        mapped = _map_status(provider=provider, raw_status=provider_status)
        link.status = mapped.value
        link.closed_at = closed_at
        link.last_synced_at = datetime.now(UTC)
        self._session.flush()

        self._audit.record(
            context=context,
            action="external_issue.sync",
            resource_type="external_issue",
            resource_id=link.id,
            payload={
                "provider": provider,
                "issue_key": issue_key,
                "raw_status": provider_status,
                "mapped_status": mapped.value,
                "raw": raw or {},
            },
        )
        return link

    # ------------------------------------------------------------ helpers

    def get(self, *, link_id: UUID) -> ExternalIssue:
        link = self._session.get(ExternalIssue, link_id)
        if link is None:
            raise ResourceNotFoundError("external_issue", link_id)
        return link

    def _lookup_recent(
        self,
        *,
        workspace_id: UUID,
        signal_id: str,
        provider: str,
        since: datetime,
    ) -> ExternalIssue | None:
        stmt = (
            select(ExternalIssue)
            .where(
                ExternalIssue.workspace_id == workspace_id,
                ExternalIssue.signal_id == signal_id,
                ExternalIssue.provider == provider,
                ExternalIssue.opened_at >= since,
            )
            .order_by(ExternalIssue.opened_at.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def _lookup_by_provider_key(self, *, provider: str, issue_key: str) -> ExternalIssue | None:
        stmt = select(ExternalIssue).where(
            ExternalIssue.provider == provider,
            ExternalIssue.issue_key == issue_key,
        )
        return self._session.scalars(stmt).first()


def _map_status(*, provider: str, raw_status: str) -> IssueStatus:
    """Resolve a provider-native status into :class:`IssueStatus`,
    falling back to ``OPEN`` for unknown values so an unexpected
    custom workflow doesn't accidentally close the link."""
    table = _PROVIDER_STATUS_MAP.get(provider, {})
    return table.get(raw_status.lower(), IssueStatus.OPEN)


__all__ = [
    "DEFAULT_DEDUP_WINDOW",
    "CreateOrReuseResult",
    "ExternalIssueService",
]
