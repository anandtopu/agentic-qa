"""Notifier Protocol + LogNotifier reference implementation.

Story 2.1.3 — the API needs to fan an approval ask out to humans
(Slack DM, email digest, in-app toast) without coupling the service
layer to any of those transports. The Protocol below is the stable
seam; transports drop in by satisfying it.

Phase 2 ships ``LogNotifier`` which writes a structured log line per
notification — enough for staging demos and easy to grep in audit
trails. Slack + SES adapters land in Phase 3 as separate modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import structlog


class NotifierError(RuntimeError):
    """A notifier transport failed. Callers may suppress this — a
    failed notification must not block an approval request from
    being persisted."""


@dataclass(slots=True, frozen=True)
class ApprovalNotification:
    """Payload handed to a Notifier when an approval row is created
    or transitions state. Kept transport-agnostic so the Protocol
    impls can format it however their channel needs."""

    request_id: UUID
    tenant_id: UUID
    workspace_id: UUID | None
    event_type: str
    state: str
    subject: str
    reason: str | None
    requested_by: UUID | None
    decided_by: UUID | None
    expires_at: datetime | None
    correlation_id: str | None
    extra: dict[str, Any]


class Notifier(Protocol):
    """The seam every transport implements."""

    def notify_requested(self, payload: ApprovalNotification) -> None: ...

    def notify_decided(self, payload: ApprovalNotification) -> None: ...


class LogNotifier:
    """Structured-log notifier — the Phase 2 default transport.

    Emits exactly two log keys (``approval.requested`` /
    ``approval.decided``) so an admin can grep for them in their
    log aggregator while the Slack/email adapters are still in
    flight.
    """

    def __init__(self, logger: Any | None = None) -> None:
        self._log = logger or structlog.get_logger("qaforge_api.notifications")

    def notify_requested(self, payload: ApprovalNotification) -> None:
        self._log.info("approval.requested", **_to_kwargs(payload))

    def notify_decided(self, payload: ApprovalNotification) -> None:
        self._log.info("approval.decided", **_to_kwargs(payload))


def _to_kwargs(payload: ApprovalNotification) -> dict[str, Any]:
    return {
        "request_id": str(payload.request_id),
        "tenant_id": str(payload.tenant_id),
        "workspace_id": (str(payload.workspace_id) if payload.workspace_id is not None else None),
        "event_type": payload.event_type,
        "state": payload.state,
        "subject": payload.subject,
        "reason": payload.reason,
        "requested_by": (str(payload.requested_by) if payload.requested_by is not None else None),
        "decided_by": (str(payload.decided_by) if payload.decided_by is not None else None),
        "expires_at": (payload.expires_at.isoformat() if payload.expires_at is not None else None),
        "correlation_id": payload.correlation_id,
        "extra": payload.extra,
    }
