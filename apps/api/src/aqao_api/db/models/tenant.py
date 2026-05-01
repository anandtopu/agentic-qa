"""Tenant — top of the multi-tenancy tree (ADR-0007).

Tenants table is itself NOT under RLS; lookup must be possible from the
authn layer to resolve a JWT-claimed tenant_id before the per-request
session variable is set.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
