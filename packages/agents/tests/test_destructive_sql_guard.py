"""Unit tests for DestructiveSqlGuard — Story 2.2.3.

AC: 100% of DELETE/UPDATE/DROP/TRUNCATE/ALTER statements require
approval before execution. We verify the guard:

* Routes destructive SQL through the approval gate (returns an
  ApprovalGateStep);
* Allows read-only SQL through (returns None);
* Raises synchronously on read-only execution paths via
  ``assert_read_only``.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest

from aqao_agents.db_validator import (
    DestructiveSqlBlocked,
    DestructiveSqlGuard,
)
from aqao_agents.runtime.approval import ApprovalDecision


class _FakeGate:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def request(
        self,
        *,
        workflow_id: UUID,
        workspace_id: UUID,
        event_type: str,
        subject: str,
        reason: str | None,
        gate_context: Mapping[str, Any],
    ) -> UUID:
        request_id = uuid.uuid4()
        self.requests.append(
            {
                "request_id": request_id,
                "event_type": event_type,
                "subject": subject,
                "gate_context": dict(gate_context),
            }
        )
        return request_id

    def lookup(self, request_id: UUID) -> ApprovalDecision:
        return ApprovalDecision(
            request_id=request_id,
            state="pending",
            decided_by=None,
            decided_at=None,
            comment=None,
        )


def test_guard_returns_none_for_read_only_sql() -> None:
    guard = DestructiveSqlGuard(gate=_FakeGate())
    step = guard.maybe_build_step(sql="SELECT * FROM users", subject="read user list")
    assert step is None


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM users WHERE id = 1",
        "UPDATE users SET name = 'x'",
        "DROP TABLE legacy",
        "TRUNCATE TABLE evidence",
        "ALTER TABLE users ADD COLUMN c text",
    ],
)
def test_guard_returns_step_for_destructive_sql(sql: str) -> None:
    """AC: every DELETE/UPDATE/DROP/TRUNCATE/ALTER routes through approval."""
    guard = DestructiveSqlGuard(gate=_FakeGate())
    step = guard.maybe_build_step(sql=sql, subject="cleanup")
    assert step is not None
    assert step.event_type == "destructive_sql"
    assert "destructive_verbs" in step.extra_context
    assert step.extra_context["statement_count"] >= 1


def test_guard_step_invokes_gate_with_destructive_context() -> None:
    """End-to-end: when the step runs, it passes the destructive verb
    list through to the ApprovalGate so the reviewer sees what they're
    being asked to approve."""
    gate = _FakeGate()
    guard = DestructiveSqlGuard(gate=gate)
    step = guard.maybe_build_step(
        sql="DELETE FROM users WHERE id = 1; DROP TABLE legacy",
        subject="cleanup migration",
        reason="legacy users + table no longer needed",
    )
    assert step is not None

    # Drive the step manually to capture the request.
    import asyncio

    from aqao_agents.runtime import StepContext

    ctx = StepContext(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )
    asyncio.run(step.run(ctx))

    assert len(gate.requests) == 1
    request = gate.requests[0]
    assert request["event_type"] == "destructive_sql"
    assert request["gate_context"]["destructive_verbs"] == ["DELETE", "DROP"]
    assert request["gate_context"]["statement_count"] == 2


def test_assert_read_only_raises_on_destructive() -> None:
    guard = DestructiveSqlGuard(gate=_FakeGate())
    with pytest.raises(DestructiveSqlBlocked) as exc:
        guard.assert_read_only("DELETE FROM users")
    assert exc.value.statements[0].leading_verb == "DELETE"


def test_assert_read_only_passes_on_select() -> None:
    DestructiveSqlGuard(gate=_FakeGate()).assert_read_only("SELECT 1")


def test_assert_read_only_blocks_unknown_verbs_too() -> None:
    """Unknown verbs are treated as destructive at the gate boundary —
    safer to demand approval than to silently let through something we
    don't understand."""
    with pytest.raises(DestructiveSqlBlocked):
        DestructiveSqlGuard(gate=_FakeGate()).assert_read_only(
            "LOCK TABLE users IN ACCESS EXCLUSIVE MODE"
        )
