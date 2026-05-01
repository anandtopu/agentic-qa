"""Flakiness API schemas — Story 3.3.1."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FlakinessWindowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int
    observations: int
    passes: int
    failures: int
    pass_rate: float
    flip_rate: float


class FlakinessSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: str
    workspace_id: UUID
    flakiness_score: float
    windows: list[FlakinessWindowResponse]
