"""Unit tests for the EvalRunner + dataset loader — Story 2.6.2."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from qaforge_eval import (
    AgentInvocation,
    EvalCase,
    EvalDataset,
    EvalRunner,
    FieldExactMatchScorer,
    LatencyBudgetScorer,
    Scorecard,
    load_dataset,
    load_jsonl,
)


def _stub_dataset() -> EvalDataset:
    return EvalDataset(
        name="example",
        version="v1",
        cases=[
            EvalCase(id="c1", inputs={}, expected={"answer": "yes"}),
            EvalCase(id="c2", inputs={}, expected={"answer": "no"}),
        ],
    )


@pytest.mark.asyncio
async def test_runner_emits_per_dimension_aggregates() -> None:
    runner = EvalRunner(
        agent_name="planner",
        scorers=[
            FieldExactMatchScorer(field="answer"),
            LatencyBudgetScorer(budget_ms=100),
        ],
    )

    async def agent_fn(case: EvalCase) -> AgentInvocation:
        return AgentInvocation(
            output=dict(case.expected),  # always correct
            latency_ms=50,
        )

    scorecard = await runner.run(dataset=_stub_dataset(), agent_fn=agent_fn)

    assert scorecard.total_cases == 2
    by_dim = {d.dimension: d for d in scorecard.dimensions}
    assert by_dim["exact_match:answer"].pass_rate == 1.0
    assert by_dim["latency_budget"].pass_rate == 1.0
    assert scorecard.overall_pass_rate == 1.0


@pytest.mark.asyncio
async def test_runner_records_partial_pass_rate() -> None:
    runner = EvalRunner(
        agent_name="planner",
        scorers=[FieldExactMatchScorer(field="answer")],
    )

    async def agent_fn(case: EvalCase) -> AgentInvocation:
        # Wrong answer for c2 only
        return AgentInvocation(output={"answer": "yes"})

    scorecard = await runner.run(dataset=_stub_dataset(), agent_fn=agent_fn)
    only = scorecard.dimensions[0]
    assert only.pass_rate == 0.5
    assert only.cases == 2
    assert pytest.approx(only.mean) == 0.5


@pytest.mark.asyncio
async def test_runner_accumulates_cost_and_latency() -> None:
    runner = EvalRunner(
        agent_name="planner",
        scorers=[FieldExactMatchScorer(field="answer")],
    )

    async def agent_fn(case: EvalCase) -> AgentInvocation:
        return AgentInvocation(
            output=dict(case.expected),
            usd_cost=Decimal("0.05"),
            latency_ms=120,
        )

    scorecard = await runner.run(dataset=_stub_dataset(), agent_fn=agent_fn)
    assert scorecard.total_usd_cost == Decimal("0.10")
    assert scorecard.total_latency_ms == 240


def test_load_jsonl_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text(
        "\n# comment\n"
        + json.dumps({"id": "a", "inputs": {}, "expected": {}})
        + "\n\n"
        + json.dumps({"id": "b", "inputs": {}, "expected": {}})
        + "\n",
        encoding="utf-8",
    )
    cases = load_jsonl(path)
    ids = [c.id for c in cases]
    assert ids == ["a", "b"]


def test_load_dataset_resolves_versioned_path(tmp_path: Path) -> None:
    (tmp_path / "planner").mkdir()
    (tmp_path / "planner" / "v3.jsonl").write_text(
        json.dumps({"id": "a", "inputs": {}, "expected": {}}) + "\n",
        encoding="utf-8",
    )
    dataset = load_dataset(base_dir=tmp_path, agent="planner", version="v3")
    assert dataset.name == "planner"
    assert dataset.version == "v3"
    assert len(dataset) == 1


def test_load_dataset_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_dataset(base_dir=tmp_path, agent="missing", version="v1")


def test_scorecard_round_trips_through_json() -> None:
    from datetime import UTC, datetime

    pin = datetime(2026, 5, 1, tzinfo=UTC)
    runner_card = Scorecard.model_validate_json(
        Scorecard(
            agent_name="x",
            dataset_name="y",
            dataset_version="v1",
            started_at=pin,
            finished_at=pin,
            total_cases=0,
            dimensions=[],
            cases=[],
        ).to_json()
    )
    assert runner_card.agent_name == "x"
