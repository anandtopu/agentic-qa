"""Test plan API schemas — Story 1.3."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from qaforge_api.db.models.test_plan import (
    TestCasePriority,
    TestCaseType,
    TestPlanStatus,
)


class TestPlanGenerateRequest(BaseModel):
    requirement_id: UUID
    existing_test_titles: list[str] = Field(default_factory=list, max_length=200)


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    type: TestCaseType
    priority: TestCasePriority
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    automation_candidate: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class TestPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    requirement_id: UUID
    summary: str
    status: TestPlanStatus
    coverage_areas: list[str]
    open_questions: list[str]
    plan_payload: dict[str, Any]
    generated_by_model: str | None
    generated_by_prompt_version: str | None
    usd_cost: int  # cents
    latency_ms: int
    created_at: datetime
    updated_at: datetime


class TestPlanListResponse(BaseModel):
    test_plans: list[TestPlanResponse]
    limit: int
    offset: int
