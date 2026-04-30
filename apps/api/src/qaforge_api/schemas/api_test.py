"""API tester response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GeneratedTestSummary(BaseModel):
    test_case_title: str
    function_name: str
    method: str
    path: str
    expected_status: int
    is_negative: bool
    requires_auth: bool


class ApiTestSuiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_plan_id: UUID
    framework: str
    module_name: str
    source_code: str = Field(min_length=1)
    tests: list[GeneratedTestSummary]
    cases_updated: int
    usd_cost_cents: int
    latency_ms: int
