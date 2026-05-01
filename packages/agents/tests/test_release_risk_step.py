"""Unit tests for ReleaseRiskScoringStep — Story 2.3.3."""

from __future__ import annotations

import uuid

import pytest

from aqao_agents.release_risk import (
    ReleaseRiskScorer,
    ReleaseRiskScoringStep,
    RiskFeatures,
)
from aqao_agents.runtime import StepContext


@pytest.mark.asyncio
async def test_step_scores_features_from_shared_state() -> None:
    step = ReleaseRiskScoringStep(scorer=ReleaseRiskScorer())
    features = RiskFeatures(
        total_tests=10,
        passed_tests=10,
        failed_tests=0,
        changed_file_count=1,
    )
    ctx = StepContext(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        shared={"risk_features": features.model_dump()},
    )
    result = await step.run(ctx)
    payload = result.output["risk_score"]
    assert "score" in payload
    assert "band" in payload
    assert "recommendation" in payload
    assert len(payload["top_drivers"]) >= 3


@pytest.mark.asyncio
async def test_step_accepts_pre_built_features_object() -> None:
    step = ReleaseRiskScoringStep(scorer=ReleaseRiskScorer())
    features = RiskFeatures(
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        changed_file_count=0,
    )
    ctx = StepContext(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        shared={"risk_features": features},
    )
    result = await step.run(ctx)
    assert result.output["risk_score"]["band"] == "low"


@pytest.mark.asyncio
async def test_step_raises_when_features_missing() -> None:
    step = ReleaseRiskScoringStep(scorer=ReleaseRiskScorer())
    ctx = StepContext(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        shared={},
    )
    with pytest.raises(ValueError, match="risk_features"):
        await step.run(ctx)
