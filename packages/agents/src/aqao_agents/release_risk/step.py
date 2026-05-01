"""ReleaseRiskScoringStep — pulls :class:`RiskFeatures` out of the
workflow's ``shared`` dict, runs the scorer, and stashes the result
back as ``risk_score`` (a dict) so downstream steps (report renderer,
PR comment) can consume it.

Story 2.3.3 wires this into the report generator and the GitHub Action
quality gate; the step itself is a thin adapter around
:class:`ReleaseRiskScorer`.
"""

from __future__ import annotations

from dataclasses import dataclass

from aqao_agents.release_risk.features import RiskFeatures
from aqao_agents.release_risk.scorer import ReleaseRiskScorer
from aqao_agents.runtime.state import RunState
from aqao_agents.runtime.step import StepContext, StepResult


@dataclass(slots=True)
class ReleaseRiskScoringStep:
    """Score a workflow's risk and stash the result in ``shared``."""

    scorer: ReleaseRiskScorer
    name: str = "release_risk_score"
    target_state: RunState | None = RunState.REPORTING
    max_attempts: int = 1
    features_key: str = "risk_features"
    output_key: str = "risk_score"

    async def run(self, ctx: StepContext) -> StepResult:
        raw = ctx.shared.get(self.features_key)
        if raw is None:
            raise ValueError(
                f"{self.name}: shared['{self.features_key}'] is missing — "
                "an upstream step must hydrate RiskFeatures before this step runs"
            )
        features = raw if isinstance(raw, RiskFeatures) else RiskFeatures.model_validate(raw)
        score = self.scorer.score(features)
        return StepResult(output={self.output_key: score.to_dict()})


__all__ = ["ReleaseRiskScoringStep"]
