"""Test plans + test cases — Story 1.3.

Each plan is generated from one requirement by the Planner agent.
``parsed`` carries the LLM-validated payload (matches PRD §9.3); the
``test_cases`` table is a denormalised projection so the API can list /
update individual cases without rewriting the whole plan.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TestCaseType(StrEnum):
    API = "api"
    UI = "ui"
    DB = "db"
    INTEGRATION = "integration"
    NEGATIVE = "negative"
    REGRESSION = "regression"
    SMOKE = "smoke"


class TestCasePriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestPlanStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TestPlan(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "test_plans"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[TestPlanStatus] = mapped_column(
        SAEnum(TestPlanStatus, name="test_plan_status", native_enum=False, length=16),
        nullable=False,
        server_default=TestPlanStatus.DRAFT.value,
    )
    coverage_areas: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    open_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    generated_by_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_by_prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    usd_cost: Mapped[float] = mapped_column(Integer, nullable=False, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class TestCase(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"

    test_plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[TestCaseType] = mapped_column(
        SAEnum(TestCaseType, name="test_case_type", native_enum=False, length=16),
        nullable=False,
    )
    priority: Mapped[TestCasePriority] = mapped_column(
        SAEnum(
            TestCasePriority,
            name="test_case_priority",
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    preconditions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    automation_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
