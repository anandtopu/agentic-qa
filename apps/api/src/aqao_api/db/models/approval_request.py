"""ApprovalRequest ORM — Story 2.1.1.

Backs PRD §9.10 human-approval gates. The state machine is:

    pending -> approved | rejected | expired | cancelled

Append-only ``decided_at`` is set when the request transitions out of
``pending``; ``expires_at`` is computed at create-time from the
workspace policy's approval TTL (defaulting to 24 h).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalEventType(StrEnum):
    """Mirrors :class:`aqao_api.policies.schema.ApprovalGate` so the
    ``approval_requests.event_type`` value matches the corresponding
    workspace-policy gate verbatim."""

    DESTRUCTIVE_SQL = "destructive_sql"
    PRODUCTION_TEST_EXECUTION = "production_test_execution"
    EXTERNAL_TICKET_CREATION = "external_ticket_creation"
    RELEASE_READINESS = "release_readiness"
    CI_PIPELINE_MODIFICATION = "ci_pipeline_modification"
    HIGH_COST_EVAL_RUN = "high_cost_eval_run"


_TERMINAL_STATES: frozenset[ApprovalState] = frozenset(
    {
        ApprovalState.APPROVED,
        ApprovalState.REJECTED,
        ApprovalState.EXPIRED,
        ApprovalState.CANCELLED,
    }
)


def is_terminal(state: ApprovalState) -> bool:
    return state in _TERMINAL_STATES


class ApprovalRequest(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=ApprovalState.PENDING.value
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
