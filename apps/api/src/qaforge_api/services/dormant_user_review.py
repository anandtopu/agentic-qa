"""DormantUserReviewService — TD-011 / Story 6.5.2.

Bridges :class:`AccessReviewService.snapshot` to the
:class:`DormantUserNotifier` so the quarterly access-review ritual
actually pings the admins on dormant users instead of leaving the
finding in the API response.

Triggered on a cadence (k8s CronJob, Lambda, or any external
scheduler hitting an admin-only route) — same pattern as
:class:`ModelLifecycleAlertService` (TD-008) and the retention
sweep. The bridge does not modify state: it sends one notification
per dormant user and returns a report the caller can audit.

Audit:
* If an :class:`AuditService` is supplied, the bridge records a
  ``access_review.dormant_users_notified`` event so the action is
  visible to compliance reviewers and shows up in the same audit
  trail the access review snapshot reads from.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from qaforge_api.auth.context import RequestContext
from qaforge_api.notifications import (
    DormantUserNotification,
    DormantUserNotifier,
)
from qaforge_api.services.access_review import (
    DEFAULT_REVIEW_WINDOW,
    AccessReviewEntry,
    AccessReviewService,
)
from qaforge_api.services.audit import AuditService


@dataclass(slots=True, frozen=True)
class DormantNotificationReport:
    """What the bridge saw and what it did about it."""

    checked_at: datetime
    window_days: int
    dormant_count: int
    notified: tuple[DormantUserNotification, ...]


class DormantUserReviewService:
    """Notify admins of dormant users surfaced by the access review."""

    def __init__(
        self,
        access_review: AccessReviewService,
        notifier: DormantUserNotifier,
        *,
        audit: AuditService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._access_review = access_review
        self._notifier = notifier
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(UTC))

    def notify_dormant_users(
        self,
        *,
        context: RequestContext,
        window: timedelta = DEFAULT_REVIEW_WINDOW,
    ) -> DormantNotificationReport:
        now = self._clock()
        snapshot = self._access_review.snapshot(
            tenant_id=context.tenant_id,
            window=window,
            now=now,
        )
        dormant_entries = [e for e in snapshot.entries if e.is_dormant]
        notified: list[DormantUserNotification] = []
        for entry in dormant_entries:
            payload = self._build_payload(
                tenant_id=context.tenant_id,
                entry=entry,
                window_days=snapshot.window_days,
                correlation_id=context.correlation_id,
            )
            self._notifier.notify_dormant(payload)
            notified.append(payload)

        if self._audit is not None and notified:
            self._audit.record(
                context=context,
                action="access_review.dormant_users_notified",
                resource_type="user",
                resource_id=None,
                payload={
                    "dormant_count": len(notified),
                    "window_days": snapshot.window_days,
                    "notified_user_ids": [str(p.user_id) for p in notified],
                },
            )

        return DormantNotificationReport(
            checked_at=now,
            window_days=snapshot.window_days,
            dormant_count=snapshot.dormant_count,
            notified=tuple(notified),
        )

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _build_payload(
        *,
        tenant_id: UUID,
        entry: AccessReviewEntry,
        window_days: int,
        correlation_id: str | None,
    ) -> DormantUserNotification:
        return DormantUserNotification(
            user_id=entry.user_id,
            tenant_id=tenant_id,
            email=entry.email,
            name=entry.name,
            role=entry.role,
            last_seen_at=entry.last_seen_at,
            review_window_days=window_days,
            correlation_id=correlation_id,
        )


__all__ = [
    "DormantNotificationReport",
    "DormantUserReviewService",
]
