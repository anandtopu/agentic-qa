"""RiskFeatures — Story 2.3.1 input pipeline (PRD §9.9).

The PRD names ten distinct signals; we model each as an explicit
field on :class:`RiskFeatures` so the scorer (Story 2.3.2) can hash
the same shape every time.

The features model is intentionally a value object — no IO. Consumers
hydrate it from existing data sources (test_runs row, GitHub PR diff,
historical incidents query) and pass it into :class:`ReleaseRiskScorer`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TestSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OwnershipSignal(StrEnum):
    """How well-owned the changed code is."""

    UNOWNED = "unowned"
    SOLO_OWNER = "solo_owner"
    TEAM_OWNED = "team_owned"


class SecuritySensitivity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskFeatures(BaseModel):
    """Snapshot of the ten PRD §9.9 inputs at scoring time.

    Every field is bounded and explicit so a regression in the upstream
    data pipeline becomes a validation error rather than silent score
    drift.
    """

    model_config = ConfigDict(extra="forbid")

    # 1. Test pass/fail results
    total_tests: int = Field(ge=0)
    passed_tests: int = Field(ge=0)
    failed_tests: int = Field(ge=0)

    # 2. Changed files and components
    changed_file_count: int = Field(ge=0)
    changed_lines_added: int = Field(default=0, ge=0)
    changed_lines_removed: int = Field(default=0, ge=0)

    # 3. Historical defect density (defects per kloc in changed area)
    historical_defect_density: float = Field(default=0.0, ge=0.0)

    # 4. Severity of failed tests
    failed_test_severities: list[TestSeverity] = Field(default_factory=list)

    # 5. Uncovered acceptance criteria
    uncovered_acceptance_criteria: int = Field(default=0, ge=0)
    total_acceptance_criteria: int = Field(default=0, ge=0)

    # 6. Flakiness score: 0..1 where 1 is "every test rerun produced a
    #    different verdict"
    flakiness_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # 7. Production incident history (incidents touching this code in
    #    the last 90d)
    recent_incident_count: int = Field(default=0, ge=0)

    # 8. Code ownership
    ownership: OwnershipSignal = OwnershipSignal.TEAM_OWNED

    # 9. Security-sensitive area indicators
    security_sensitivity: SecuritySensitivity = SecuritySensitivity.NONE

    # 10. Untested high-risk modules — reviewer-supplied list of
    #     modules touched but not covered by any test in the run.
    untested_high_risk_modules: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_test_counts(self) -> RiskFeatures:
        if self.passed_tests + self.failed_tests > self.total_tests:
            raise ValueError("passed + failed cannot exceed total_tests")
        if self.uncovered_acceptance_criteria > self.total_acceptance_criteria:
            raise ValueError(
                "uncovered_acceptance_criteria cannot exceed total_acceptance_criteria"
            )
        return self

    @property
    def fail_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.failed_tests / self.total_tests

    @property
    def critical_failure_count(self) -> int:
        return sum(
            1
            for s in self.failed_test_severities
            if s in {TestSeverity.HIGH, TestSeverity.CRITICAL}
        )

    @property
    def acceptance_coverage(self) -> float:
        if self.total_acceptance_criteria == 0:
            return 1.0
        return 1.0 - (self.uncovered_acceptance_criteria / self.total_acceptance_criteria)


__all__ = [
    "OwnershipSignal",
    "RiskFeatures",
    "SecuritySensitivity",
    "TestSeverity",
]
