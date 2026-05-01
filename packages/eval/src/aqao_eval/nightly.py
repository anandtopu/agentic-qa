"""Nightly multi-agent eval runner — Story 3.5.1.

The Phase-2 eval CLI runs one agent against one dataset version and
optionally diffs the result against a baseline. Story 3.5.1 wraps that
mechanism so a scheduled run can:

* enumerate every (agent, dataset_version) pinned in a config;
* drive the existing :class:`EvalRunner` + agent_fn for each;
* persist a per-agent scorecard plus a single :class:`NightlyReport`
  rolling those into one artifact;
* hand the artifact to a :class:`TrendStore` (Story 3.5.2) for history.

The runner is **agent-agnostic** — it takes a callable
``agent_fn_factory(agent_name) -> AgentFn`` so a real deployment can
plug the production registry while tests pass a stub. This keeps the
nightly contract testable without spinning up the API.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aqao_eval.datasets import EvalDataset, load_dataset
from aqao_eval.gate import BaselineGate, GateReport
from aqao_eval.runner import AgentFn, EvalRunner
from aqao_eval.scorers import Scorer
from aqao_eval.types import Scorecard


@dataclass(slots=True, frozen=True)
class NightlyTarget:
    """One agent + dataset to evaluate during a nightly run."""

    agent: str
    dataset_version: str
    baseline_path: Path | None = None
    tolerance: float = 0.0


@dataclass(slots=True, frozen=True)
class NightlyAgentResult:
    """Per-agent outcome of one nightly run."""

    agent: str
    dataset_version: str
    scorecard: Scorecard
    gate_report: GateReport | None
    baseline_present: bool

    @property
    def has_regressions(self) -> bool:
        return self.gate_report is not None and self.gate_report.has_regressions

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "dataset_version": self.dataset_version,
            "baseline_present": self.baseline_present,
            "has_regressions": self.has_regressions,
            "overall_pass_rate": self.scorecard.overall_pass_rate,
            "scorecard": _scorecard_dict(self.scorecard),
            "regressions": [
                {
                    "dimension": f.dimension,
                    "metric": f.metric,
                    "delta": f.delta,
                }
                for f in (self.gate_report.regressions if self.gate_report is not None else ())
            ],
        }


@dataclass(slots=True, frozen=True)
class NightlyReport:
    """Aggregate of every per-agent result from one nightly run."""

    started_at: datetime
    finished_at: datetime
    results: tuple[NightlyAgentResult, ...] = field(default_factory=tuple)

    @property
    def has_regressions(self) -> bool:
        return any(r.has_regressions for r in self.results)

    @property
    def regressed_agents(self) -> tuple[str, ...]:
        return tuple(r.agent for r in self.results if r.has_regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "has_regressions": self.has_regressions,
            "regressed_agents": list(self.regressed_agents),
            "results": [r.to_dict() for r in self.results],
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"nightly eval finished at {self.finished_at.isoformat()}",
            f"agents evaluated: {len(self.results)}",
        ]
        if not self.has_regressions:
            lines.append("no regressions detected.")
            return lines
        lines.append(
            f"{len(self.regressed_agents)} agent(s) regressed: {', '.join(self.regressed_agents)}"
        )
        for r in self.results:
            if not r.has_regressions or r.gate_report is None:
                continue
            lines.append(f"  --- {r.agent} ---")
            lines.extend(f"  {line}" for line in r.gate_report.summary_lines())
        return lines


AgentFnFactory = Callable[[str], AgentFn]
ScorerFactory = Callable[[str], Sequence[Scorer]]


@dataclass(slots=True)
class NightlyRunner:
    """Drives one nightly multi-agent eval run."""

    datasets_dir: Path
    agent_fn_factory: AgentFnFactory
    scorer_factory: ScorerFactory

    async def run(
        self,
        targets: Iterable[NightlyTarget],
    ) -> NightlyReport:
        started = datetime.now(UTC)
        results: list[NightlyAgentResult] = []
        for target in targets:
            results.append(await self._run_one(target))
        finished = datetime.now(UTC)
        return NightlyReport(
            started_at=started,
            finished_at=finished,
            results=tuple(results),
        )

    async def _run_one(self, target: NightlyTarget) -> NightlyAgentResult:
        dataset: EvalDataset = load_dataset(
            base_dir=self.datasets_dir,
            agent=target.agent,
            version=target.dataset_version,
        )
        runner = EvalRunner(
            agent_name=target.agent,
            scorers=list(self.scorer_factory(target.agent)),
        )
        scorecard = await runner.run(
            dataset=dataset,
            agent_fn=self.agent_fn_factory(target.agent),
        )

        gate_report: GateReport | None = None
        baseline_present = False
        if target.baseline_path is not None:
            baseline = BaselineGate.load_optional(target.baseline_path)
            if baseline is not None:
                baseline_present = True
                gate = BaselineGate(tolerance=target.tolerance)
                gate_report = gate.compare(baseline=baseline, branch=scorecard)
        return NightlyAgentResult(
            agent=target.agent,
            dataset_version=target.dataset_version,
            scorecard=scorecard,
            gate_report=gate_report,
            baseline_present=baseline_present,
        )


def run_nightly(
    *,
    datasets_dir: Path,
    targets: Iterable[NightlyTarget],
    agent_fn_factory: AgentFnFactory,
    scorer_factory: ScorerFactory,
) -> NightlyReport:
    """Sync convenience wrapper — schedules the async runner and
    returns the aggregated :class:`NightlyReport`."""
    runner = NightlyRunner(
        datasets_dir=datasets_dir,
        agent_fn_factory=agent_fn_factory,
        scorer_factory=scorer_factory,
    )
    return asyncio.run(runner.run(targets))


def _scorecard_dict(card: Scorecard) -> dict[str, Any]:
    """Compact scorecard dict for the trend artifact — strips
    per-case payloads to keep the rolling history small."""
    return {
        "agent_name": card.agent_name,
        "dataset_name": card.dataset_name,
        "dataset_version": card.dataset_version,
        "started_at": card.started_at.isoformat(),
        "finished_at": card.finished_at.isoformat(),
        "total_cases": card.total_cases,
        "overall_pass_rate": card.overall_pass_rate,
        "dimensions": [
            {
                "dimension": d.dimension,
                "cases": d.cases,
                "mean": d.mean,
                "p50": d.p50,
                "pass_rate": d.pass_rate,
            }
            for d in card.dimensions
        ],
    }


__all__ = [
    "AgentFnFactory",
    "NightlyAgentResult",
    "NightlyReport",
    "NightlyRunner",
    "NightlyTarget",
    "ScorerFactory",
    "run_nightly",
]
