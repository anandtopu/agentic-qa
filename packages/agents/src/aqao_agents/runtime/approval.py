"""ApprovalGateStep — Story 2.1.2.

Pauses a workflow on a human-approval gate (PRD §9.10) and resumes
when the request reaches a terminal state. The step does not depend
on the Control Plane directly — it talks to an :class:`ApprovalGate`
Protocol that the API layer wires to its real ``ApprovalService``.

Usage flow:

1. First execution — there is no approval row yet for this workflow +
   gate. The step calls ``gate.request(...)``, stashes the resulting
   id under ``shared['approval_request_id']``, and returns
   ``StepResult(pause=True)``. The runner persists the workflow in
   ``PAUSED_FOR_APPROVAL``.
2. A reviewer decides the request through whichever surface (REST,
   Slack, UI). The decision is durable in ``approval_requests``.
3. The workflow is re-driven (resume). On re-entry the step sees the
   stashed id, calls ``gate.lookup(...)``, and:
   - ``approved`` -> emits the approval payload to ``shared`` and
     completes the step normally.
   - ``rejected``/``cancelled``/``expired`` -> raises
     :class:`ApprovalDenied` so the runner records the workflow as
     failed.
   - ``pending`` -> pauses again. Idempotent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from aqao_agents.runtime.state import RunState
from aqao_agents.runtime.step import StepContext, StepResult

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXPIRED = "expired"
CANCELLED = "cancelled"

_TERMINAL_DENIALS: frozenset[str] = frozenset({REJECTED, EXPIRED, CANCELLED})


class ApprovalDenied(RuntimeError):  # noqa: N818 - public name predates rule
    """A gate decision was negative — workflow should fail."""

    def __init__(self, *, request_id: UUID, state: str, comment: str | None) -> None:
        super().__init__(f"approval request {request_id} ended in state {state!r}")
        self.request_id = request_id
        self.state = state
        self.comment = comment


@dataclass(slots=True)
class ApprovalDecision:
    """Snapshot of the gate row read on resume — small enough to pass
    through ``shared`` without coupling to ORM types."""

    request_id: UUID
    state: str
    decided_by: UUID | None
    decided_at: datetime | None
    comment: str | None


class ApprovalGate(Protocol):
    """Surface the workflow runtime needs from the Control Plane."""

    def request(
        self,
        *,
        workflow_id: UUID,
        workspace_id: UUID,
        event_type: str,
        subject: str,
        reason: str | None,
        gate_context: Mapping[str, Any],
    ) -> UUID: ...

    def lookup(self, request_id: UUID) -> ApprovalDecision: ...


@dataclass(slots=True)
class ApprovalGateStep:
    """Step that pauses the workflow on a human approval gate."""

    name: str
    event_type: str
    subject: str
    gate: ApprovalGate
    reason: str | None = None
    target_state: RunState | None = RunState.PAUSED_FOR_APPROVAL
    max_attempts: int = 1
    extra_context: dict[str, Any] = field(default_factory=dict)
    shared_key: str = "approval_request_id"

    async def run(self, ctx: StepContext) -> StepResult:
        existing_id = _coerce_uuid(ctx.shared.get(self.shared_key))
        if existing_id is None:
            request_id = self.gate.request(
                workflow_id=ctx.workflow_id,
                workspace_id=ctx.workspace_id,
                event_type=self.event_type,
                subject=self.subject,
                reason=self.reason,
                gate_context=self._build_context(ctx),
            )
            return StepResult(
                output={self.shared_key: str(request_id)},
                pause=True,
            )

        decision = self.gate.lookup(existing_id)
        if decision.state == PENDING:
            return StepResult(pause=True)
        if decision.state in _TERMINAL_DENIALS:
            raise ApprovalDenied(
                request_id=decision.request_id,
                state=decision.state,
                comment=decision.comment,
            )
        if decision.state == APPROVED:
            return StepResult(
                output={
                    "approval_state": decision.state,
                    "approval_decided_by": (
                        str(decision.decided_by) if decision.decided_by is not None else None
                    ),
                    "approval_decided_at": (
                        decision.decided_at.isoformat() if decision.decided_at is not None else None
                    ),
                    "approval_comment": decision.comment,
                },
            )
        # Defensive — surface unknown states explicitly rather than
        # silently treating them as approval.
        raise ApprovalDenied(
            request_id=decision.request_id,
            state=decision.state,
            comment=decision.comment,
        )

    def _build_context(self, ctx: StepContext) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "workflow_id": str(ctx.workflow_id),
            "step_name": self.name,
        }
        if ctx.correlation_id is not None:
            merged["correlation_id"] = ctx.correlation_id
        merged.update(self.extra_context)
        return merged


def _coerce_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


__all__ = [
    "APPROVED",
    "CANCELLED",
    "EXPIRED",
    "PENDING",
    "REJECTED",
    "ApprovalDecision",
    "ApprovalDenied",
    "ApprovalGate",
    "ApprovalGateStep",
]
