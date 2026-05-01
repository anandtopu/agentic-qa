"""Failure-classifier types — input :class:`FailureSignal`, output
:class:`Classification` (PRD §9.8 schema)."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FailureCategory(StrEnum):
    PRODUCT_DEFECT = "product_defect"
    TEST_ISSUE = "test_issue"
    ENVIRONMENT_ISSUE = "environment_issue"
    FLAKY_TEST = "flaky_test"
    DATA_ISSUE = "data_issue"
    UNKNOWN = "unknown"


class ClassificationSource(StrEnum):
    HEURISTIC = "heuristic"
    LLM = "llm"


class FailureSignal(BaseModel):
    """One observed failure waiting to be classified."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1, max_length=200)
    test_name: str | None = Field(default=None, max_length=500)
    agent_name: str | None = Field(default=None, max_length=100)
    tool: str | None = Field(default=None, max_length=100)
    error_message: str = Field(default="", max_length=10_000)
    stdout_excerpt: str = Field(default="", max_length=8_000)
    stderr_excerpt: str = Field(default="", max_length=8_000)
    http_status_code: int | None = Field(default=None, ge=0, le=599)
    duration_ms: int | None = Field(default=None, ge=0)
    # Story 3.3.2 — caller-supplied flakiness signal (flip-rate over the
    # 14-day rolling window from FlakinessService). 0.0 means stable;
    # values >= 0.3 push the classifier toward FLAKY_TEST and away from
    # PRODUCT_DEFECT to reduce false positives (PRD §19 target < 15%).
    flakiness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def composite_text(self) -> str:
        """All searchable text from the signal joined for regex matchers."""
        parts = [
            self.test_name or "",
            self.error_message,
            self.stdout_excerpt,
            self.stderr_excerpt,
        ]
        return "\n".join(p for p in parts if p)


class Classification(BaseModel):
    """Single classification output for one :class:`FailureSignal`."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str
    category: FailureCategory
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    classified_by: ClassificationSource
    rule: str | None = None
    reasoning: str = Field(min_length=1, max_length=4_000)
    suggested_fix: str | None = Field(default=None, max_length=2_000)
    model: str | None = None
    prompt_version: str | None = None
