"""FailureClassification — Story 1.7.

One row per classified failure signal. The combined agent runs the
heuristic pre-classifier first; if a rule fires, ``classified_by`` is
``heuristic`` and ``model`` is null. Otherwise we record the LLM
classification with the model + prompt version that produced it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    CreatedAtMixin,
    TenantScopedMixin,
    UUIDPrimaryKeyMixin,
)


class FailureCategory(StrEnum):
    PRODUCT_DEFECT = "product_defect"
    TEST_ISSUE = "test_issue"
    ENVIRONMENT_ISSUE = "environment_issue"
    FLAKY_TEST = "flaky_test"
    DATA_ISSUE = "data_issue"
    UNKNOWN = "unknown"


class ClassifiedBy(StrEnum):
    HEURISTIC = "heuristic"
    LLM = "llm"


class FailureClassification(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "failure_classifications"

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
    signal_id: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[FailureCategory] = mapped_column(
        SAEnum(
            FailureCategory,
            name="failure_category",
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default="0.00"
    )
    classified_by: Mapped[ClassifiedBy] = mapped_column(
        SAEnum(
            ClassifiedBy,
            name="failure_classified_by",
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    rule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_signal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
