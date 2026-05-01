"""Agent feedback schemas — Story 6.3.1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackRatingValue(StrEnum):
    UP = "up"
    DOWN = "down"


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    agent_kind: str = Field(min_length=1, max_length=64)
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: UUID
    rating: FeedbackRatingValue
    comment: str | None = Field(default=None, max_length=4000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace_id: UUID
    agent_kind: str
    resource_type: str
    resource_id: UUID
    rating: FeedbackRatingValue
    comment: str | None
    submitted_by_user_id: UUID | None
    submitted_at: datetime
    eval_case_id: str | None
    eval_case_path: str | None
    converted_at: datetime | None


class FeedbackListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FeedbackResponse]


class LowRatedReviewEntry(BaseModel):
    """One agent's slice of the rolling low-rated review."""

    model_config = ConfigDict(extra="forbid")

    agent_kind: str
    total_feedback: int = Field(ge=0)
    down_count: int = Field(ge=0)
    up_count: int = Field(ge=0)
    down_rate: float = Field(ge=0.0, le=1.0)
    pending_conversion: int = Field(ge=0)
    converted: int = Field(ge=0)
    conversion_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of negatively-rated feedback already converted into eval cases.",
    )


class LowRatedReviewResponse(BaseModel):
    """Rolling-window summary used for the weekly review ritual."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    window_days: int = Field(ge=1)
    since: datetime
    overall_down_count: int = Field(ge=0)
    overall_total: int = Field(ge=0)
    overall_conversion_rate: float = Field(ge=0.0, le=1.0)
    by_agent: list[LowRatedReviewEntry]
    pending_items: list[FeedbackResponse]


class EvalConversionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: UUID
    eval_case_id: str
    eval_case_path: str
    agent_kind: str
    converted_at: datetime


__all__ = [
    "EvalConversionResult",
    "FeedbackCreateRequest",
    "FeedbackListResponse",
    "FeedbackRatingValue",
    "FeedbackResponse",
    "LowRatedReviewEntry",
    "LowRatedReviewResponse",
]
