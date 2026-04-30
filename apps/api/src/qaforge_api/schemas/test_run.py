"""Test run API schemas — Story 1.6."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from qaforge_api.db.models.test_run import AgentTaskState, TestRunState


class TestRunStartRequest(BaseModel):
    test_plan_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=64)


class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    test_run_id: UUID
    agent_name: str
    step_index: int
    state: AgentTaskState
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int
    attempt: int
    error: str | None


class TestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    test_plan_id: UUID | None
    requirement_id: UUID | None
    state: TestRunState
    idempotency_key: str
    triggered_by: UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    summary: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


class TestRunListResponse(BaseModel):
    runs: list[TestRunResponse]
    limit: int
    offset: int


class TestRunStartResponse(BaseModel):
    run: TestRunResponse
    final_state: TestRunState
    steps_executed: int
    paused: bool
