"""AccessReviewService — Story 6.5.2.

Snapshots ``(user, role, last_seen_at, recent_action_count)`` for
the quarterly access review described in Epic 6.5. The result is
the answer to "who currently has what — and have they been using
it?" — the standard SOC-2 access review question.

``last_seen_at`` is derived from the audit trail (Story 2.4.1 +
3.1.2). The classifier is intentionally simple: the latest
``audit_events.created_at`` for each user inside a configurable
review window. Users with no audit-event activity in the window
get ``last_seen_at=None`` and ``recent_action_count=0`` — those
are the access-review action items.

The service does not modify any state; it's a read-only query
designed to be exposed to admins for export / sign-off.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qaforge_api.db.models import AuditEvent, User

DEFAULT_REVIEW_WINDOW = timedelta(days=90)


@dataclass(frozen=True, slots=True)
class AccessReviewEntry:
    user_id: UUID
    email: str
    name: str
    role: str
    last_seen_at: datetime | None
    recent_action_count: int

    @property
    def is_dormant(self) -> bool:
        """True when the user has no audit activity in the review window."""
        return self.recent_action_count == 0


@dataclass(frozen=True, slots=True)
class AccessReviewSnapshot:
    tenant_id: UUID
    window_days: int
    since: datetime
    entries: tuple[AccessReviewEntry, ...]

    @property
    def dormant_count(self) -> int:
        return sum(1 for e in self.entries if e.is_dormant)


class AccessReviewService:
    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    def snapshot(
        self,
        *,
        tenant_id: UUID,
        window: timedelta = DEFAULT_REVIEW_WINDOW,
        now: datetime | None = None,
    ) -> AccessReviewSnapshot:
        moment = now or self._clock()
        since = moment - window
        users = self._fetch_users(tenant_id=tenant_id)
        activity = self._fetch_activity(tenant_id=tenant_id, since=since)

        entries = tuple(
            AccessReviewEntry(
                user_id=user.id,
                email=user.email,
                name=user.name,
                role=user.role,
                last_seen_at=activity.get(user.id, (None, 0))[0],
                recent_action_count=activity.get(user.id, (None, 0))[1],
            )
            for user in users
        )
        return AccessReviewSnapshot(
            tenant_id=tenant_id,
            window_days=int(window.total_seconds() // 86400) or 1,
            since=since,
            entries=entries,
        )

    # ---------------------------------------------------- helpers

    def _fetch_users(self, *, tenant_id: UUID) -> list[User]:
        stmt = (
            select(User)
            .where(User.tenant_id == tenant_id)
            .order_by(User.email.asc())
        )
        return list(self._session.scalars(stmt).all())

    def _fetch_activity(
        self, *, tenant_id: UUID, since: datetime
    ) -> dict[UUID, tuple[datetime, int]]:
        """Per-user (latest_event_at, count) inside the review window."""
        stmt = (
            select(
                AuditEvent.actor_user_id,
                func.max(AuditEvent.created_at).label("last_seen_at"),
                func.count().label("recent_count"),
            )
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.created_at >= since,
                AuditEvent.actor_user_id.isnot(None),
            )
            .group_by(AuditEvent.actor_user_id)
        )
        out: dict[UUID, tuple[datetime, int]] = {}
        for row in self._session.execute(stmt).all():
            user_id = row[0]
            last_seen = row[1]
            count = int(row[2] or 0)
            if user_id is None:
                continue
            out[user_id] = (last_seen, count)
        return out


__all__ = [
    "DEFAULT_REVIEW_WINDOW",
    "AccessReviewEntry",
    "AccessReviewService",
    "AccessReviewSnapshot",
]
