"""Planner output schema — mirrors PRD §9.3 verbatim.

Re-defined here in the agents package (not imported from
``aqao_api``) so the agent has no dependency on the Control Plane.
The two enums match by value with the API-side ones.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TestCaseType(StrEnum):
    API = "api"
    UI = "ui"
    DB = "db"
    INTEGRATION = "integration"
    NEGATIVE = "negative"
    REGRESSION = "regression"
    SMOKE = "smoke"


class TestCasePriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlannerTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    type: TestCaseType
    priority: TestCasePriority = TestCasePriority.MEDIUM
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list, min_length=1)
    expected_result: str = Field(min_length=1)
    automation_candidate: bool = True
    tags: list[str] = Field(default_factory=list)


class PlannerTestPlan(BaseModel):
    """The structured output every Planner call must produce."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    coverage_areas: list[str] = Field(default_factory=list)
    test_cases: list[PlannerTestCase] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)
