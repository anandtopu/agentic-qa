"""Evidence-report API schemas — Story 1.8."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aqao_agents.reporter import GoNoGo


class GenerateReportRequest(BaseModel):
    recommendation: GoNoGo = GoNoGo.NEEDS_REVIEW
    recommendation_reasoning: str = Field(default="", max_length=2_000)


class EvidenceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: UUID
    test_run_id: UUID
    sha256: str
    size_bytes: int
    storage_key: str
    markdown: str
    signed_url: str | None
    signed_url_expires_at: datetime | None
