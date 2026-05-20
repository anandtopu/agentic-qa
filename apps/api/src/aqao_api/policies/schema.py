"""AgentPolicy — Pydantic mirror of PRD §10.3.

The PRD example::

    policy:
      allow_write_operations: false
      require_approval_for:
        - destructive_sql
        - production_test_execution
        - external_ticket_creation
      redact_secrets: true
      max_cost_usd_per_run: 5.00
      max_runtime_minutes: 30

The Policy Guard agent (PRD §10.1) enforces these at run time; this
module is just the source of truth for the schema.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalGate(StrEnum):
    DESTRUCTIVE_SQL = "destructive_sql"
    PRODUCTION_TEST_EXECUTION = "production_test_execution"
    EXTERNAL_TICKET_CREATION = "external_ticket_creation"
    RELEASE_READINESS = "release_readiness"
    CI_PIPELINE_MODIFICATION = "ci_pipeline_modification"
    HIGH_COST_EVAL_RUN = "high_cost_eval_run"


# Data classes a workspace may override the retention window for. This is the
# subset of RetentionSweepService's registry that (a) is not compliance-locked
# and (b) carries a direct ``workspace_id`` column, so a per-workspace window
# can be applied without a join. Keep in sync with
# ``aqao_api.services.retention.DEFAULT_RETENTION_CLASSES`` — the guard test
# ``test_retention_service.test_overridable_classes_match_registry`` enforces it.
OVERRIDABLE_RETENTION_CLASSES: frozenset[str] = frozenset(
    {
        "test_runs",
        "flakiness_observations",
        "agent_feedback",
        "external_issues",
        "usage_records",
    }
)

# The data-handling policy commits to a 365-day maximum retention window; a
# workspace override may not exceed it.
RETENTION_MAX_DAYS = 365


class AgentPolicy(BaseModel):
    """Workspace agent policy.

    Validated on every save. The Policy Guard reads the active version
    at run start and applies it for the duration of that run; in-flight
    workflows are not retroactively re-validated.
    """

    model_config = ConfigDict(extra="forbid")

    allow_write_operations: bool = False
    require_approval_for: list[ApprovalGate] = Field(default_factory=list)
    redact_secrets: bool = True
    max_cost_usd_per_run: Decimal = Field(default=Decimal("5.00"), gt=Decimal("0"))
    max_runtime_minutes: int = Field(default=30, gt=0, le=24 * 60)
    retention: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Per-data-class retention overrides, in days. Keys must be one of "
            "OVERRIDABLE_RETENTION_CLASSES; values are 1..RETENTION_MAX_DAYS. "
            "Classes omitted here fall back to the platform default window. "
            "Compliance-locked classes (e.g. audit events) cannot be overridden."
        ),
    )

    @model_validator(mode="after")
    def _no_duplicate_gates(self) -> AgentPolicy:
        if len(self.require_approval_for) != len(set(self.require_approval_for)):
            raise ValueError("require_approval_for must not contain duplicates")
        return self

    @model_validator(mode="after")
    def _validate_retention(self) -> AgentPolicy:
        for cls_name, days in self.retention.items():
            if cls_name not in OVERRIDABLE_RETENTION_CLASSES:
                raise ValueError(
                    f"retention override {cls_name!r} is not an overridable data "
                    f"class; choose from {sorted(OVERRIDABLE_RETENTION_CLASSES)}"
                )
            if not 1 <= days <= RETENTION_MAX_DAYS:
                raise ValueError(
                    f"retention.{cls_name} must be between 1 and "
                    f"{RETENTION_MAX_DAYS} days, got {days}"
                )
        return self


DEFAULT_POLICY_YAML = """\
policy:
  allow_write_operations: false
  require_approval_for:
    - destructive_sql
    - production_test_execution
    - external_ticket_creation
  redact_secrets: true
  max_cost_usd_per_run: 5.00
  max_runtime_minutes: 30
"""
