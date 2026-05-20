"""Compliance schemas — Stories 6.5.1 + 6.5.2."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetentionSweepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=False,
        description=(
            "If true, count what would be deleted but commit no changes. "
            "Compliance-locked classes are reported as skipped either way."
        ),
    )


class ClassSweepResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    cutoff: datetime
    default_days: int = Field(ge=1)
    compliance_locked: bool
    deleted: int = Field(ge=0)
    would_delete: int = Field(ge=0)
    skipped_reason: str | None
    override_workspaces: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of workspaces whose own retention window was applied to "
            "this class (0 = default window only). The cutoff shown is the "
            "default-window cutoff; override buckets use their own windows."
        ),
    )


class SweepReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    dry_run: bool
    total_deleted: int = Field(ge=0)
    total_would_delete: int = Field(ge=0)
    classes: list[ClassSweepResultResponse]


class AccessReviewEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    name: str
    role: str
    last_seen_at: datetime | None
    recent_action_count: int = Field(ge=0)
    is_dormant: bool


class AccessReviewSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    window_days: int = Field(ge=1)
    since: datetime
    entries: list[AccessReviewEntryResponse]
    dormant_count: int = Field(ge=0)


__all__ = [
    "AccessReviewEntryResponse",
    "AccessReviewSnapshotResponse",
    "ClassSweepResultResponse",
    "RetentionSweepRequest",
    "SweepReportResponse",
]
