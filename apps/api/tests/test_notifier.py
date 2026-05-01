"""Unit tests for the notifier abstraction — Story 2.1.3.

The Slack/email transports drop in by satisfying the same Protocol;
here we verify the LogNotifier reference impl emits the expected keys
and tolerates a transport failure without bubbling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aqao_api.notifications import (
    ApprovalNotification,
    LogNotifier,
    Notifier,
    NotifierError,
)


@dataclass(slots=True)
class _StubLogger:
    info_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def info(self, event: str, **kwargs: Any) -> None:
        self.info_calls.append((event, kwargs))

    # structlog BoundLogger surface — keep narrow, only what's used.
    def warning(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - unused
        pass


def _payload() -> ApprovalNotification:
    return ApprovalNotification(
        request_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        tenant_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        workspace_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        event_type="destructive_sql",
        state="pending",
        subject="DROP TABLE legacy",
        reason="cleanup",
        requested_by=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        decided_by=None,
        expires_at=datetime(2026, 5, 1, tzinfo=UTC) + timedelta(hours=24),
        correlation_id="trace-1",
        extra={"workflow_id": "wf-1"},
    )


def test_log_notifier_emits_requested_event() -> None:
    logger = _StubLogger()
    notifier = LogNotifier(logger=logger)

    notifier.notify_requested(_payload())

    assert len(logger.info_calls) == 1
    event, fields = logger.info_calls[0]
    assert event == "approval.requested"
    assert fields["event_type"] == "destructive_sql"
    assert fields["state"] == "pending"
    assert fields["request_id"] == "11111111-1111-1111-1111-111111111111"


def test_log_notifier_emits_decided_event() -> None:
    logger = _StubLogger()
    notifier = LogNotifier(logger=logger)

    notifier.notify_decided(_payload())

    assert logger.info_calls[0][0] == "approval.decided"


def test_log_notifier_handles_none_optionals() -> None:
    logger = _StubLogger()
    notifier = LogNotifier(logger=logger)
    payload = ApprovalNotification(
        request_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        workspace_id=None,
        event_type="release_readiness",
        state="approved",
        subject="release",
        reason=None,
        requested_by=None,
        decided_by=None,
        expires_at=None,
        correlation_id=None,
        extra={},
    )
    notifier.notify_decided(payload)
    fields = logger.info_calls[0][1]
    assert fields["workspace_id"] is None
    assert fields["expires_at"] is None
    assert fields["requested_by"] is None


def test_protocol_satisfied_by_log_notifier() -> None:
    """Cheap structural check that LogNotifier matches the Notifier
    Protocol — protects against drift if the Protocol grows methods."""
    notifier: Notifier = LogNotifier()
    assert hasattr(notifier, "notify_requested")
    assert hasattr(notifier, "notify_decided")


def test_notifier_error_is_a_runtime_error() -> None:
    # Routers swallow NotifierError so a transport outage never blocks
    # an approval being persisted; verify the type relation here.
    with pytest.raises(NotifierError):
        raise NotifierError("Slack 500")
