"""Test runs + agent tasks + evidence artifacts — Epic 1.6.

Three tables introduced in lockstep because the orchestrator (Story
1.6.1) writes all three in a single workflow execution: a ``test_run``
parent row, one ``agent_task`` per workflow step, and zero or more
``evidence_artifacts`` produced by the steps.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    CreatedAtMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TestRunState(StrEnum):
    PLANNED = "planned"
    EXECUTING = "executing"
    CLASSIFYING = "classifying"
    REPORTING = "reporting"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    DONE = "done"
    FAILED = "failed"


class AgentTaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestRun(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_test_runs_workspace_idempotency",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[TestRunState] = mapped_column(
        SAEnum(TestRunState, name="test_run_state", native_enum=False, length=32),
        nullable=False,
        server_default=TestRunState.PLANNED.value,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentTask(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        UniqueConstraint(
            "test_run_id",
            "step_index",
            name="uq_agent_tasks_run_step_index",
        ),
    )

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[AgentTaskState] = mapped_column(
        SAEnum(AgentTaskState, name="agent_task_state", native_enum=False, length=16),
        nullable=False,
        server_default=AgentTaskState.PENDING.value,
    )
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvidenceArtifact(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "test_run_id",
            "sha256",
            "original_filename",
            name="uq_evidence_run_sha_filename",
        ),
    )

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
