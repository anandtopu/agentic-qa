"""PR comment API schemas — Story 1.9.2."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_signed_url: str | None = Field(default=None, max_length=2_000)
    run_url: str | None = Field(default=None, max_length=2_000)


class PrCommentResponse(BaseModel):
    test_run_id: UUID
    body: str
    marker: str
