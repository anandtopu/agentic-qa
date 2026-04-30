"""Notifier abstraction — Story 2.1.3.

Phase 2 ships a single :class:`LogNotifier` implementation. Slack and
email transports drop in by satisfying the same Protocol.
"""

from __future__ import annotations

from qaforge_api.notifications.notifier import (
    ApprovalNotification,
    LogNotifier,
    Notifier,
    NotifierError,
)

__all__ = [
    "ApprovalNotification",
    "LogNotifier",
    "Notifier",
    "NotifierError",
]
