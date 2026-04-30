"""CLI entry point for the eval harness — wired to ``make eval``.

Phase 2 ships the harness mechanics + a tiny smoke dataset; once
Story 2.6.1's golden datasets land (≥50 cases per agent), this CLI
gains an ``--agent`` selector and the runner is invoked per-agent in
sequence.

Usage
-----

    python -m qaforge_eval.cli run \\
        --baseline=docs/eval/baseline.json \\
        --output=.scorecards/branch.json \\
        --datasets=packages/eval/datasets

    python -m qaforge_eval.cli set-baseline \\
        --scorecard=.scorecards/branch.json \\
        --baseline=docs/eval/baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from qaforge_eval.datasets import load_dataset
from qaforge_eval.gate import BaselineGate
from qaforge_eval.runner import AgentInvocation, EvalRunner
from qaforge_eval.scorers import (
    CostBudgetScorer,
    LatencyBudgetScorer,
)
from qaforge_eval.types import EvalCase, Scorecard


async def _stub_agent(case: EvalCase) -> AgentInvocation:
    """Phase-2 placeholder agent.

    Echoes the expected output with a fixed latency / cost so the
    harness is exercisable end-to-end before real agents are wired
    in. Replace with a registry call (``--agent planner``) when the
    real datasets land in Story 2.6.1.
    """
    return AgentInvocation(
        output=dict(case.expected),
        usd_cost=case.metadata.get("expected_cost_usd", 0),
        latency_ms=int(case.metadata.get("expected_latency_ms", 0)),
    )


def _build_runner(agent: str) -> EvalRunner:
    return EvalRunner(
        agent_name=agent,
        scorers=[
            LatencyBudgetScorer(budget_ms=60_000),
            CostBudgetScorer(budget_usd=__import__("decimal").Decimal("0.50")),
        ],
        prompt_version=None,
        model="stub-eval",
    )


async def _run(args: argparse.Namespace) -> int:
    datasets_dir: Path = args.datasets
    output: Path = args.output
    baseline: Path = args.baseline

    dataset = load_dataset(base_dir=datasets_dir, agent=args.agent, version=args.dataset_version)
    runner = _build_runner(args.agent)
    scorecard = await runner.run(dataset=dataset, agent_fn=_stub_agent)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(scorecard.to_json(), encoding="utf-8")
    print(f"wrote scorecard to {output}")

    baseline_card = BaselineGate.load_optional(baseline)
    if baseline_card is None:
        print(f"no baseline at {baseline} — skipping regression check")
        return 0

    gate = BaselineGate(tolerance=args.tolerance)
    report = gate.compare(baseline=baseline_card, branch=scorecard)
    for line in report.summary_lines():
        print(line)
    return 1 if report.has_regressions else 0


def _set_baseline(args: argparse.Namespace) -> int:
    scorecard: Path = args.scorecard
    baseline: Path = args.baseline
    card = Scorecard.model_validate_json(scorecard.read_text("utf-8"))
    BaselineGate.write_baseline(baseline, card)
    print(f"wrote {baseline}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qaforge-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the eval harness against a dataset.")
    run.add_argument("--agent", default="example")
    run.add_argument("--dataset-version", default="v1")
    run.add_argument(
        "--datasets",
        type=Path,
        default=Path("packages/eval/datasets"),
    )
    run.add_argument(
        "--output",
        type=Path,
        default=Path(".scorecards/branch.json"),
    )
    run.add_argument(
        "--baseline",
        type=Path,
        default=Path("docs/eval/baseline.json"),
    )
    run.add_argument("--tolerance", type=float, default=0.0)

    sb = sub.add_parser("set-baseline", help="Promote a scorecard to be the baseline.")
    sb.add_argument("--scorecard", type=Path, required=True)
    sb.add_argument("--baseline", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return asyncio.run(_run(args))
    if args.cmd == "set-baseline":
        return _set_baseline(args)
    raise SystemExit(parser.error(f"unknown command: {args.cmd}"))


if __name__ == "__main__":
    sys.exit(main())
