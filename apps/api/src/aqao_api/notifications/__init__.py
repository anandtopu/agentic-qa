"""Notifier abstractions.

* :class:`Notifier` (Story 2.1.3) — fans approval state changes out
  to humans (Slack / email / in-app).
* :class:`DormantUserNotifier` (TD-011 / Story 6.5.2) — fans
  access-review dormant-user findings to admins so the quarterly
  ritual actually escalates.

Phase 2 ships log-only reference implementations
(:class:`LogNotifier`, :class:`LogDormantUserNotifier`); real
transports drop in by satisfying the same Protocols.
"""

from __future__ import annotations

from aqao_api.notifications.dormant_user import (
    DormantUserNotification,
    DormantUserNotifier,
    LogDormantUserNotifier,
)
from aqao_api.notifications.notifier import (
    ApprovalNotification,
    LogNotifier,
    Notifier,
    NotifierError,
)

__all__ = [
    "ApprovalNotification",
    "DormantUserNotification",
    "DormantUserNotifier",
    "LogDormantUserNotifier",
    "LogNotifier",
    "Notifier",
    "NotifierError",
]
