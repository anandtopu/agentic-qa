"""Workflow state enum (mirrors ``TestRunState`` on the Control Plane)."""

from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    PLANNED = "planned"
    EXECUTING = "executing"
    CLASSIFYING = "classifying"
    REPORTING = "reporting"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    DONE = "done"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {RunState.DONE, RunState.FAILED}
