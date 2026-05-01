"""Typed input shapes for the report renderer.

The renderer accepts ``RunReportContext`` and emits Markdown. Every
field has a stable default so adding a new section in a future epic
doesn't break older fixture snapshots.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GoNoGo(StrEnum):
    GO = "go"
    NO_GO = "no_go"
    NEEDS_REVIEW = "needs_review"


class CoverageArea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    case_count: int = Field(ge=0)
    passed: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)


class TestCaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    type: str
    priority: str
    automation_candidate: bool = True
    status: str = "pending"  # passed / failed / skipped / pending


class FailureSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    category: str
    confidence: Decimal
    classified_by: str
    rule: str | None = None
    reasoning: str
    suggested_fix: str | None = None


class ArtifactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str  # trace | video | screenshot | report | other
    filename: str
    sha256: str
    size_bytes: int
    signed_url: str | None = None
    signed_url_expires_at: datetime | None = None


class AgentTraceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_index: int
    agent_name: str
    state: str  # succeeded | failed | running | pending
    duration_ms: int = 0
    attempt: int = 1
    error_excerpt: str | None = None


class RunReportContext(BaseModel):
    """Typed context for the renderer; one field per PRD §9.11 section."""

    model_config = ConfigDict(extra="forbid")

    workspace_name: str
    test_run_id: UUID
    test_plan_summary: str = ""
    state: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0

    # Scope / coverage
    coverage_areas: list[CoverageArea] = Field(default_factory=list)
    test_cases: list[TestCaseSummary] = Field(default_factory=list)

    # Pass/fail summary (denormalised from test_cases for readability)
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    # Failure classification breakdown (PRD §9.11)
    failures: list[FailureSummary] = Field(default_factory=list)
    failure_category_counts: dict[str, int] = Field(default_factory=dict)
    heuristic_ratio: Decimal = Field(default=Decimal("0"))

    # Risk score (Phase 2 fills it in; null is fine here)
    risk_score: float | None = None
    risk_drivers: list[str] = Field(default_factory=list)

    # Evidence
    artifacts: list[ArtifactSummary] = Field(default_factory=list)

    # Agent traces (one line per workflow step)
    agent_trace: list[AgentTraceLine] = Field(default_factory=list)

    # Cost & latency
    total_usd_cost_cents: int = 0
    total_latency_ms: int = 0

    # Open questions (Story 1.3.2 + LLM)
    open_questions: list[str] = Field(default_factory=list)

    # Human approvals (Phase 2 — empty in Phase 1)
    approvals: list[str] = Field(default_factory=list)

    # Go/no-go recommendation
    recommendation: GoNoGo = GoNoGo.NEEDS_REVIEW
    recommendation_reasoning: str = ""

    # Metadata
    generated_at: datetime
    template_version: str = "1.0.0"
