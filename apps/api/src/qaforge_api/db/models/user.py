"""User — a human or service principal scoped to one tenant."""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class User(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
