"""ModelRegistryEntry ORM — Story 6.2.1.

One row per (tenant, provider, model_id). Tracks the Phase-6 model
lifecycle:

* ``status`` — ``candidate`` (registered, not yet decided),
  ``pinned`` (decision: ``go``; production traffic may use it),
  ``rejected`` (decision: ``no_go``), ``deprecated`` (was pinned,
  scheduled for removal).
* ``decision`` is set when an operator records the go/no-go.
* ``deprecation_at`` schedules sunset for a previously-pinned model.

The 14-day SLA from Epic 6.2 ("decision recorded within 14 days of
release") is enforced by ``ModelLifecycleService.awaiting_decision``,
which uses the partial index in migration ``0016`` to keep the query
cheap as the registry grows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ModelLifecycleStatus(StrEnum):
    CANDIDATE = "candidate"
    PINNED = "pinned"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class ModelDecision(StrEnum):
    GO = "go"
    NO_GO = "no_go"


class ModelRegistryEntry(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "model_id",
            name="uq_model_registry_tenant_provider_model",
        ),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    released_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=ModelLifecycleStatus.CANDIDATE.value,
    )
    eval_scorecard_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eval_scorecard_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(8), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deprecation_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


__all__ = [
    "ModelDecision",
    "ModelLifecycleStatus",
    "ModelRegistryEntry",
]
