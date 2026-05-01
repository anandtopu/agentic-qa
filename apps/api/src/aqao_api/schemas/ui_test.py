"""UI tester response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GeneratedUiTestSummary(BaseModel):
    test_case_title: str
    title: str
    journey_steps: list[str]
    expected_outcome: str
    requires_auth: bool


class FragilityFindingResponse(BaseModel):
    line_number: int
    snippet: str
    rule: str
    severity: str
    suggestion: str


class UiTestSpecResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_plan_id: UUID
    framework: str
    spec_filename: str
    source_code: str = Field(min_length=1)
    tests: list[GeneratedUiTestSummary]
    fragility_findings: list[FragilityFindingResponse]
    cases_updated: int
    usd_cost_cents: int
    latency_ms: int
