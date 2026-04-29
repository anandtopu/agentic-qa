"""AuditEvent — append-only audit trail (PRD §14.4 + Epic 2.4).

Phase 1 ships the writer; Phase 2 Story 2.4.1 adds per-row HMAC signing
so tampering breaks signature verification. Schema below leaves space
for ``signature`` so the upgrade is additive.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    CreatedAtMixin,
    TenantScopedMixin,
    UUIDPrimaryKeyMixin,
)


class AuditEvent(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
