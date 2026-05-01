"""Wire types for the eval harness.

Stable across runs so a Scorecard JSON file from yesterday is still
readable today. Versioned via :data:`SCORECARD_VERSION`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCORECARD_VERSION = "1.0.0"


class EvalCase(BaseModel):
    """One row of a JSONL dataset."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    inputs: dict[str, Any]
    expected: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    """One scorer's verdict on one case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    dimension: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DimensionAggregate(BaseModel):
    """Aggregate score for one dimension across the whole dataset."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    cases: int = Field(ge=0)
    mean: float = Field(ge=0.0, le=1.0)
    p50: float = Field(ge=0.0, le=1.0)
    pass_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of cases where score == 1.0.",
    )


class Scorecard(BaseModel):
    """Top-level Scorecard JSON written by ``make eval``."""

    model_config = ConfigDict(extra="forbid")

    version: str = SCORECARD_VERSION
    agent_name: str
    dataset_name: str
    dataset_version: str
    prompt_version: str | None = None
    model: str | None = None
    started_at: datetime
    finished_at: datetime
    total_cases: int = Field(ge=0)
    total_usd_cost: Decimal = Decimal("0")
    total_latency_ms: int = 0
    dimensions: list[DimensionAggregate]
    cases: list[ScoreResult]

    @property
    def overall_pass_rate(self) -> float:
        if not self.dimensions:
            return 0.0
        return sum(d.pass_rate for d in self.dimensions) / len(self.dimensions)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)
