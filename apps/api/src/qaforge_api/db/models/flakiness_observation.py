"""FlakinessObservation ORM — Story 3.3.1.

Append-only ledger of (test_id, passed) outcomes. Rolling pass-rates
over 14/30/90-day windows are computed by :class:`FlakinessService` —
this model is just the durable storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    TenantScopedMixin,
    UUIDPrimaryKeyMixin,
)


class FlakinessObservation(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "flakiness_observations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_id: Mapped[str] = mapped_column(String(500), nullable=False)
    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
