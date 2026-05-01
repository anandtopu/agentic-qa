"""Release Risk Scoring Agent — Epic 2.3.

Produces a release readiness score from objective QA signals
(PRD §9.9). Pipeline:

    RiskFeatures -> ReleaseRiskScorer -> RiskScore + drivers + go/no-go

Public surface:

* :class:`RiskFeatures` — Pydantic model holding the ten PRD inputs.
* :class:`ReleaseRiskScorer` — weighted rubric v1.
* :class:`RiskScore`, :class:`RiskBand`, :class:`RiskDriver`,
  :class:`Recommendation` — result types.
"""

from aqao_agents.release_risk.features import (
    OwnershipSignal,
    RiskFeatures,
    SecuritySensitivity,
    TestSeverity,
)
from aqao_agents.release_risk.scorer import (
    DEFAULT_DRIVER_WEIGHTS,
    DEFAULT_THRESHOLDS,
    Recommendation,
    ReleaseRiskScorer,
    RiskBand,
    RiskDriver,
    RiskScore,
    RiskThresholds,
)
from aqao_agents.release_risk.step import ReleaseRiskScoringStep

__all__ = [
    "DEFAULT_DRIVER_WEIGHTS",
    "DEFAULT_THRESHOLDS",
    "OwnershipSignal",
    "Recommendation",
    "ReleaseRiskScorer",
    "ReleaseRiskScoringStep",
    "RiskBand",
    "RiskDriver",
    "RiskFeatures",
    "RiskScore",
    "RiskThresholds",
    "SecuritySensitivity",
    "TestSeverity",
]
