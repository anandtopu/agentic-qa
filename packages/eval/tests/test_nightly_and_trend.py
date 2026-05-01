"""Continuous-eval regression suite tests — Stories 3.5.1 / 3.5.2 / 3.5.3.

Covers:

* :class:`NightlyRunner` aggregates every target into one
  :class:`NightlyReport` and surfaces the regressed agents.
* :class:`FilesystemTrendStore` round-trips entries + payloads via the
  ``index.jsonl`` tail-read path.
* :class:`RegressionAlertEmitter` fires a ``gate_regression`` alert on
  the current-run regression and a ``trend_decline`` alert when the
  rolling window shows a strict decline > threshold.
* AC verification: a planted prompt regression (degraded ``agent_fn``)
  flips ``has_regressions`` to ``True`` within one nightly cycle.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aqao_eval import (
    AgentInvocation,
    BaselineGate,
    EvalCase,
    EvalDataset,
    FieldExactMatchScorer,
    FilesystemTrendStore,
    NightlyRunner,
    NightlyTarget,
    RegressionAlert,
    RegressionAlertEmitter,
    Scorer,
    TrendEntry,
)


def _ds(version: str = "v1") -> EvalDataset:
    return EvalDataset(
        name="planner",
        version=version,
        cases=[EvalCase(id=f"c-{i}", inputs={}, expected={"answer": "ok"}) for i in range(5)],
    )


async def _good_agent(case: EvalCase) -> AgentInvocation:
    return AgentInvocation(output={"answer": "ok"})


async def _bad_agent(case: EvalCase) -> AgentInvocation:
    """Planted regression — wrong answer for every case."""
    return AgentInvocation(output={"answer": "WRONG"})


def _scorers(_: str) -> list[Scorer]:
    return [FieldExactMatchScorer(field="answer")]


def _datasets_dir(tmp_path: Path) -> Path:
    """Lay out a `planner/v1.jsonl` dataset matching ``_ds()`` so the
    nightly runner's load_dataset call succeeds. Idempotent: tests that
    call it multiple times in the same tmp_path get the same layout."""
    base = tmp_path / "datasets"
    (base / "planner").mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps({"id": f"c-{i}", "inputs": {}, "expected": {"answer": "ok"}}) for i in range(5)
    )
    (base / "planner" / "v1.jsonl").write_text(payload, encoding="utf-8")
    return base


# ---------------------------------------------------------------- nightly


@pytest.mark.asyncio
async def test_nightly_runs_every_target_and_aggregates(tmp_path: Path) -> None:
    runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _good_agent,
        scorer_factory=_scorers,
    )
    report = await runner.run([NightlyTarget(agent="planner", dataset_version="v1")])
    assert len(report.results) == 1
    assert report.results[0].scorecard.overall_pass_rate == 1.0
    assert not report.has_regressions


@pytest.mark.asyncio
async def test_nightly_skips_gate_when_baseline_missing(tmp_path: Path) -> None:
    runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _good_agent,
        scorer_factory=_scorers,
    )
    report = await runner.run(
        [
            NightlyTarget(
                agent="planner",
                dataset_version="v1",
                baseline_path=tmp_path / "missing.json",
            )
        ]
    )
    result = report.results[0]
    assert result.gate_report is None
    assert not result.baseline_present


@pytest.mark.asyncio
async def test_nightly_summary_lines_describe_regressions(tmp_path: Path) -> None:
    """Plant a baseline with 100% pass rate, run the bad agent, expect
    the summary to call out the regression."""
    runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _good_agent,
        scorer_factory=_scorers,
    )
    baseline_path = tmp_path / "baselines" / "planner.json"
    baseline_report = await runner.run([NightlyTarget(agent="planner", dataset_version="v1")])
    BaselineGate.write_baseline(baseline_path, baseline_report.results[0].scorecard)

    bad_runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _bad_agent,
        scorer_factory=_scorers,
    )
    report = await bad_runner.run(
        [
            NightlyTarget(
                agent="planner",
                dataset_version="v1",
                baseline_path=baseline_path,
            )
        ]
    )
    assert report.has_regressions
    text = "\n".join(report.summary_lines())
    assert "planner" in text
    assert "regress" in text.lower()


# ---------------------------------------------------------------- trend store


def test_filesystem_trend_store_round_trips(tmp_path: Path) -> None:
    store = FilesystemTrendStore(root=tmp_path / "trends")
    entry = TrendEntry(
        agent="planner",
        run_id="r-1",
        finished_at=datetime(2026, 5, 1, tzinfo=UTC),
        overall_pass_rate=0.95,
        has_regressions=False,
    )
    store.append(entry, payload={"hello": "world"})

    history = store.history(agent="planner", limit=10)
    assert len(history) == 1
    assert history[0].run_id == "r-1"
    assert history[0].overall_pass_rate == 0.95

    artifact = (tmp_path / "trends" / "planner" / "r-1.json").read_text(encoding="utf-8")
    assert "hello" in artifact


def test_filesystem_trend_store_history_returns_in_chronological_order(
    tmp_path: Path,
) -> None:
    store = FilesystemTrendStore(root=tmp_path / "trends")
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i, rate in enumerate([0.8, 0.9, 0.7]):
        store.append(
            TrendEntry(
                agent="planner",
                run_id=f"r-{i}",
                finished_at=base + timedelta(days=i),
                overall_pass_rate=rate,
                has_regressions=False,
            ),
            payload={"i": i},
        )
    history = store.history(agent="planner", limit=5)
    assert [e.run_id for e in history] == ["r-0", "r-1", "r-2"]


def test_filesystem_trend_store_handles_unsafe_agent_names(tmp_path: Path) -> None:
    """Agent names with path separators must not escape the root."""
    store = FilesystemTrendStore(root=tmp_path / "trends")
    store.append(
        TrendEntry(
            agent="../etc",
            run_id="r-1",
            finished_at=datetime(2026, 5, 1, tzinfo=UTC),
            overall_pass_rate=1.0,
            has_regressions=False,
        ),
        payload={},
    )
    # Sanitised path stays inside root — `../etc` collapses to `_etc`,
    # neutralising the parent-directory traversal.
    assert (tmp_path / "trends" / "_etc" / "r-1.json").exists()
    # And of course the literal `../etc/r-1.json` does NOT exist.
    assert not (tmp_path / "etc" / "r-1.json").exists()


# ---------------------------------------------------------------- alerts


class _StubSink:
    def __init__(self) -> None:
        self.alerts: list[RegressionAlert] = []

    def emit(self, alert: RegressionAlert) -> None:
        self.alerts.append(alert)


@pytest.mark.asyncio
async def test_emitter_fires_gate_regression_alert(tmp_path: Path) -> None:
    """AC verification: a planted prompt regression (bad_agent) lands
    a gate_regression alert in one nightly cycle."""
    runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _good_agent,
        scorer_factory=_scorers,
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_report = await runner.run([NightlyTarget(agent="planner", dataset_version="v1")])
    BaselineGate.write_baseline(baseline_path, baseline_report.results[0].scorecard)

    bad_runner = NightlyRunner(
        datasets_dir=_datasets_dir(tmp_path),
        agent_fn_factory=lambda _agent: _bad_agent,
        scorer_factory=_scorers,
    )
    report = await bad_runner.run(
        [
            NightlyTarget(
                agent="planner",
                dataset_version="v1",
                baseline_path=baseline_path,
            )
        ]
    )

    sink = _StubSink()
    emitter = RegressionAlertEmitter(
        store=FilesystemTrendStore(root=tmp_path / "trends"),
        sink=sink,
    )
    alerts = emitter.consume(run_id=str(uuid.uuid4()), report=report)
    assert any(a.kind == "gate_regression" for a in alerts)
    assert sink.alerts and sink.alerts[0].agent == "planner"


def test_emitter_fires_trend_decline_after_window_of_drops(
    tmp_path: Path,
) -> None:
    """Three consecutive declining pass-rates cross the 5% threshold
    and trigger a trend_decline alert."""
    store = FilesystemTrendStore(root=tmp_path / "trends")
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i, rate in enumerate([0.95, 0.90, 0.80]):
        store.append(
            TrendEntry(
                agent="planner",
                run_id=f"r-{i}",
                finished_at=base + timedelta(days=i),
                overall_pass_rate=rate,
                has_regressions=False,
            ),
            payload={},
        )

    sink = _StubSink()
    emitter = RegressionAlertEmitter(store=store, sink=sink, window=3)
    # Build a synthetic NightlyReport with no per-run regression so we
    # only check the trend path.
    from aqao_eval.nightly import NightlyAgentResult, NightlyReport
    from aqao_eval.types import Scorecard

    card = Scorecard(
        agent_name="planner",
        dataset_name="planner",
        dataset_version="v1",
        started_at=base + timedelta(days=3),
        finished_at=base + timedelta(days=3),
        total_cases=0,
        dimensions=[],
        cases=[],
    )
    report = NightlyReport(
        started_at=base + timedelta(days=3),
        finished_at=base + timedelta(days=3),
        results=(
            NightlyAgentResult(
                agent="planner",
                dataset_version="v1",
                scorecard=card,
                gate_report=None,
                baseline_present=False,
            ),
        ),
    )
    # The current run also has a low pass-rate that continues the
    # decline (overall_pass_rate=0.0 from empty dimensions).
    alerts = emitter.consume(run_id="r-3", report=report)
    decline = [a for a in alerts if a.kind == "trend_decline"]
    assert decline, "expected a trend_decline alert after consecutive drops"


def test_emitter_does_not_alert_when_window_not_yet_full(tmp_path: Path) -> None:
    """Two data points isn't enough — the emitter must not fire on a
    half-formed window."""
    store = FilesystemTrendStore(root=tmp_path / "trends")
    base = datetime(2026, 5, 1, tzinfo=UTC)
    store.append(
        TrendEntry(
            agent="planner",
            run_id="r-0",
            finished_at=base,
            overall_pass_rate=0.95,
            has_regressions=False,
        ),
        payload={},
    )
    sink = _StubSink()
    emitter = RegressionAlertEmitter(store=store, sink=sink, window=3)

    from aqao_eval.nightly import NightlyAgentResult, NightlyReport
    from aqao_eval.types import Scorecard

    card = Scorecard(
        agent_name="planner",
        dataset_name="planner",
        dataset_version="v1",
        started_at=base + timedelta(days=1),
        finished_at=base + timedelta(days=1),
        total_cases=0,
        dimensions=[],
        cases=[],
    )
    report = NightlyReport(
        started_at=base + timedelta(days=1),
        finished_at=base + timedelta(days=1),
        results=(
            NightlyAgentResult(
                agent="planner",
                dataset_version="v1",
                scorecard=card,
                gate_report=None,
                baseline_present=False,
            ),
        ),
    )
    alerts = emitter.consume(run_id="r-1", report=report)
    assert not any(a.kind == "trend_decline" for a in alerts)


def test_emitter_does_not_alert_when_decline_below_threshold(
    tmp_path: Path,
) -> None:
    """A gentle decline (1pp/run) below the 5% threshold does not fire.

    Uses a synthetic scorecard with a realistic pass-rate so the
    current run continues the gentle slope rather than crashing to 0.
    """
    store = FilesystemTrendStore(root=tmp_path / "trends")
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i, rate in enumerate([0.95, 0.94]):
        store.append(
            TrendEntry(
                agent="planner",
                run_id=f"r-{i}",
                finished_at=base + timedelta(days=i),
                overall_pass_rate=rate,
                has_regressions=False,
            ),
            payload={},
        )

    sink = _StubSink()
    emitter = RegressionAlertEmitter(store=store, sink=sink, window=3, decline_threshold=0.05)
    from aqao_eval.nightly import NightlyAgentResult, NightlyReport
    from aqao_eval.types import DimensionAggregate, Scorecard

    card = Scorecard(
        agent_name="planner",
        dataset_name="planner",
        dataset_version="v1",
        started_at=base + timedelta(days=2),
        finished_at=base + timedelta(days=2),
        total_cases=10,
        dimensions=[
            DimensionAggregate(
                dimension="exact_match:answer",
                cases=10,
                mean=0.93,
                p50=0.93,
                pass_rate=0.93,
            )
        ],
        cases=[],
    )
    report = NightlyReport(
        started_at=base + timedelta(days=2),
        finished_at=base + timedelta(days=2),
        results=(
            NightlyAgentResult(
                agent="planner",
                dataset_version="v1",
                scorecard=card,
                gate_report=None,
                baseline_present=False,
            ),
        ),
    )
    alerts = emitter.consume(run_id="r-2", report=report)
    assert not any(a.kind == "trend_decline" for a in alerts)
