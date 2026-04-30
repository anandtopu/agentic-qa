"""Model lifecycle schemas — Story 6.2.1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelLifecycleStatusValue(StrEnum):
    CANDIDATE = "candidate"
    PINNED = "pinned"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class ModelDecisionValue(StrEnum):
    GO = "go"
    NO_GO = "no_go"


class ModelRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
    family: str | None = Field(default=None, max_length=64)
    released_at: datetime


class AttachScorecardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eval_scorecard_id: str = Field(min_length=1, max_length=128)
    eval_scorecard_path: str | None = Field(default=None, max_length=500)


class ModelDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ModelDecisionValue
    rationale: str = Field(min_length=1, max_length=4000)


class ModelDeprecationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deprecation_at: datetime


class ModelRegistryEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider: str
    model_id: str
    family: str | None
    released_at: datetime
    status: ModelLifecycleStatusValue
    eval_scorecard_id: str | None
    eval_scorecard_path: str | None
    decision: ModelDecisionValue | None
    decision_rationale: str | None
    decision_at: datetime | None
    decided_by_user_id: UUID | None
    deprecation_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ModelRegistryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ModelRegistryEntryResponse]


class AwaitingDecisionEntry(BaseModel):
    """One row of the awaiting-decision SLA report."""

    model_config = ConfigDict(extra="forbid")

    entry: ModelRegistryEntryResponse
    age_days: int = Field(ge=0)
    sla_breached: bool


class AwaitingDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sla_days: int = Field(ge=1)
    items: list[AwaitingDecisionEntry]
    breach_count: int = Field(ge=0)


__all__ = [
    "AttachScorecardRequest",
    "AwaitingDecisionEntry",
    "AwaitingDecisionResponse",
    "ModelDecisionRequest",
    "ModelDecisionValue",
    "ModelDeprecationRequest",
    "ModelLifecycleStatusValue",
    "ModelRegisterRequest",
    "ModelRegistryEntryResponse",
    "ModelRegistryListResponse",
]
