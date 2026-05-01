"""Dormant-user notifier — TD-011 / Story 6.5.2.

The :class:`AccessReviewService` reports who has been dormant for
the configured review window, but Phase-6 left the "actually tell
someone" half unwired. This module is that half: a Protocol that
mirrors the approval :class:`Notifier` (Story 2.1.3) for the
quarterly access-review ritual, plus a structured-log reference
implementation suitable for the staging deploy.

Real Slack / SES transports drop in by satisfying the Protocol; the
bridge service in :mod:`aqao_api.services.dormant_user_review`
calls them once per dormant user so the transport layer can decide
whether to digest or fan out one DM per row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import structlog


@dataclass(slots=True, frozen=True)
class DormantUserNotification:
    """Payload handed to a :class:`DormantUserNotifier`.

    Mirrors the shape of :class:`ApprovalNotification` (Story 2.1.3)
    so a single Slack/email transport can format both with shared
    helpers without coupling the dataclasses themselves.
    """

    user_id: UUID
    tenant_id: UUID
    email: str
    name: str
    role: str
    last_seen_at: datetime | None
    review_window_days: int
    correlation_id: str | None = None


class DormantUserNotifier(Protocol):
    """The seam every transport implements."""

    def notify_dormant(self, payload: DormantUserNotification) -> None: ...


class LogDormantUserNotifier:
    """Structured-log notifier — emits one ``access_review.dormant_user``
    line per dormant user.

    Same convention as :class:`LogNotifier` (approvals) and
    :class:`LogPageNotifier` (incidents) — staging-grade logging that
    a downstream aggregator can route on the event key alone.
    """

    def __init__(self, logger: Any | None = None) -> None:
        self._log = logger or structlog.get_logger("aqao_api.notifications")

    def notify_dormant(self, payload: DormantUserNotification) -> None:
        self._log.info("access_review.dormant_user", **_to_kwargs(payload))


def _to_kwargs(payload: DormantUserNotification) -> dict[str, Any]:
    return {
        "user_id": str(payload.user_id),
        "tenant_id": str(payload.tenant_id),
        "email": payload.email,
        "name": payload.name,
        "role": payload.role,
        "last_seen_at": (
            payload.last_seen_at.isoformat() if payload.last_seen_at is not None else None
        ),
        "review_window_days": payload.review_window_days,
        "correlation_id": payload.correlation_id,
    }


__all__ = [
    "DormantUserNotification",
    "DormantUserNotifier",
    "LogDormantUserNotifier",
]
