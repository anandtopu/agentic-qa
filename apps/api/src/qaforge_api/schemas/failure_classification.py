"""Failure classification API schemas — Story 1.7."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from qaforge_agents.classifier import FailureSignal
from qaforge_api.db.models.failure_classification import (
    ClassifiedBy,
    FailureCategory,
)


class ClassifyFailuresRequest(BaseModel):
    signals: list[FailureSignal] = Field(min_length=1, max_length=200)


class FailureClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    test_run_id: UUID
    agent_task_id: UUID | None
    signal_id: str
    category: FailureCategory
    confidence: Decimal
    classified_by: ClassifiedBy
    rule: str | None
    reasoning: str
    suggested_fix: str | None
    raw_signal: dict[str, Any]
    model: str | None
    prompt_version: str | None
    created_at: datetime


class ClassifyFailuresResponse(BaseModel):
    test_run_id: UUID
    classifications: list[FailureClassificationResponse]
    heuristic_ratio: Decimal
    llm_call_count: int
    total_usd_cost_cents: int
