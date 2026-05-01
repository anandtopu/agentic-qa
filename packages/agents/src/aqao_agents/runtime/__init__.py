"""Workflow runtime — Story 1.6.1.

ADR-0002 commits the platform to **LangGraph** as the agent orchestration
runtime, wrapped behind an internal facade so consumers depend on our
types, not LangGraph's. This module is that facade.

Phase 1 ships an in-process state machine that satisfies the same
contract as a future LangGraph implementation (Step / Graph / state
checkpointing). Phase 2 will swap the engine to LangGraph behind the
same names without touching call sites.
"""

from aqao_agents.runtime.approval import (
    ApprovalDecision,
    ApprovalDenied,
    ApprovalGate,
    ApprovalGateStep,
)
from aqao_agents.runtime.graph import WorkflowGraph
from aqao_agents.runtime.persistence import (
    InMemoryWorkflowStore,
    StoredStep,
    StoredWorkflow,
    WorkflowStore,
)
from aqao_agents.runtime.runner import (
    StepFailed,
    WorkflowExecutionError,
    WorkflowRunner,
    WorkflowRunResult,
)
from aqao_agents.runtime.state import RunState
from aqao_agents.runtime.step import (
    Step,
    StepContext,
    StepFn,
    StepResult,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalDenied",
    "ApprovalGate",
    "ApprovalGateStep",
    "InMemoryWorkflowStore",
    "RunState",
    "Step",
    "StepContext",
    "StepFailed",
    "StepFn",
    "StepResult",
    "StoredStep",
    "StoredWorkflow",
    "WorkflowExecutionError",
    "WorkflowGraph",
    "WorkflowRunResult",
    "WorkflowRunner",
    "WorkflowStore",
]
