"""Eval runner — orchestrates dataset x agent x scorers into a :class:`Scorecard`."""

from __future__ import annotations

import statistics
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from qaforge_eval.datasets import EvalDataset
from qaforge_eval.scorers import Scorer
from qaforge_eval.types import (
    DimensionAggregate,
    EvalCase,
    Scorecard,
    ScoreResult,
)


@dataclass(slots=True)
class AgentInvocation:
    """What the agent returned for one case.

    ``output`` is what the scorers consume. ``usd_cost`` and
    ``latency_ms`` flow into the scorecard's totals (and are also
    accessible to budget scorers via ``output["latency_ms"]`` /
    ``output["usd_cost"]``).
    """

    output: dict[str, Any]
    usd_cost: Decimal = Decimal("0")
    latency_ms: int = 0


AgentFn = Callable[[EvalCase], Awaitable[AgentInvocation]]


@dataclass(slots=True)
class EvalRunner:
    agent_name: str
    scorers: Sequence[Scorer]
    prompt_version: str | None = None
    model: str | None = None

    async def run(
        self,
        *,
        dataset: EvalDataset,
        agent_fn: AgentFn,
    ) -> Scorecard:
        started = datetime.now(UTC)

        case_results: list[ScoreResult] = []
        per_dimension: dict[str, list[float]] = {s.dimension: [] for s in self.scorers}
        total_cost = Decimal("0")
        total_latency = 0

        for case in dataset:
            invocation = await agent_fn(case)
            total_cost += invocation.usd_cost
            total_latency += invocation.latency_ms

            scoring_input = dict(invocation.output)
            scoring_input.setdefault("latency_ms", invocation.latency_ms)
            scoring_input.setdefault("usd_cost", str(invocation.usd_cost))

            for scorer in self.scorers:
                result = scorer.score(case, scoring_input)
                case_results.append(result)
                per_dimension.setdefault(result.dimension, []).append(result.score)

        finished = datetime.now(UTC)
        dimensions = [_aggregate(name, scores) for name, scores in per_dimension.items()]

        return Scorecard(
            agent_name=self.agent_name,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            prompt_version=self.prompt_version,
            model=self.model,
            started_at=started,
            finished_at=finished,
            total_cases=len(dataset),
            total_usd_cost=total_cost,
            total_latency_ms=total_latency,
            dimensions=dimensions,
            cases=case_results,
        )


def _aggregate(dimension: str, scores: list[float]) -> DimensionAggregate:
    if not scores:
        return DimensionAggregate(dimension=dimension, cases=0, mean=0.0, p50=0.0, pass_rate=0.0)
    return DimensionAggregate(
        dimension=dimension,
        cases=len(scores),
        mean=statistics.fmean(scores),
        p50=statistics.median(scores),
        pass_rate=sum(1 for s in scores if s >= 0.999) / len(scores),
    )
