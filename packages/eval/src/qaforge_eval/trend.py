"""Trend store + regression alert — Story 3.5.2.

A :class:`TrendStore` keeps a rolling history of nightly scorecards
keyed by ``(agent, run_id)``. The reference implementation is a
filesystem layout — production deployments can plug an S3 / DB impl
behind the same Protocol.

A :class:`RegressionAlertEmitter` watches the freshly-finished
:class:`NightlyReport`, adds the latest scorecard to the trend store,
and fires structured alerts when:

1. The current run has a regression past tolerance (the gate already
   detected this; this layer just turns it into an alert);
2. The agent's overall pass-rate has been declining for ``window``
   consecutive runs by more than ``decline_threshold``.

The emitter never raises — alert delivery (Slack, PagerDuty) is
plugged in via an :class:`AlertSink` Protocol with a structured-log
sink as the default.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import structlog

from qaforge_eval.nightly import NightlyAgentResult, NightlyReport


@dataclass(slots=True, frozen=True)
class TrendEntry:
    """One historical data point for a single agent."""

    agent: str
    run_id: str
    finished_at: datetime
    overall_pass_rate: float
    has_regressions: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "run_id": self.run_id,
            "finished_at": self.finished_at.isoformat(),
            "overall_pass_rate": self.overall_pass_rate,
            "has_regressions": self.has_regressions,
        }


class TrendStore(Protocol):
    """Append history; query the last N entries for an agent."""

    def append(self, entry: TrendEntry, payload: dict[str, Any]) -> None: ...

    def history(self, *, agent: str, limit: int) -> list[TrendEntry]: ...


@dataclass(slots=True)
class FilesystemTrendStore:
    """Reference TrendStore — one JSON file per (agent, run_id)
    under ``root / agent /``, plus a flat ``index.jsonl`` per agent
    for fast tail-reads.

    Production deployments can swap this for an S3 / DB impl by
    satisfying the :class:`TrendStore` Protocol.
    """

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, entry: TrendEntry, payload: dict[str, Any]) -> None:
        agent_dir = self.root / _safe_agent(entry.agent)
        agent_dir.mkdir(parents=True, exist_ok=True)
        artifact = agent_dir / f"{entry.run_id}.json"
        artifact.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        index = agent_dir / "index.jsonl"
        with index.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict()) + "\n")

    def history(self, *, agent: str, limit: int) -> list[TrendEntry]:
        index = self.root / _safe_agent(agent) / "index.jsonl"
        if not index.exists():
            return []
        entries: list[TrendEntry] = []
        with index.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                entries.append(
                    TrendEntry(
                        agent=raw["agent"],
                        run_id=raw["run_id"],
                        finished_at=datetime.fromisoformat(raw["finished_at"]),
                        overall_pass_rate=raw["overall_pass_rate"],
                        has_regressions=raw["has_regressions"],
                    )
                )
        entries.sort(key=lambda e: e.finished_at)
        return entries[-limit:]


_SAFE_AGENT_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _safe_agent(name: str) -> str:
    """Sanitise an agent name for use as a path segment.

    Strips anything outside ``[A-Za-z0-9_-]`` so ``..`` / path
    separators / spaces can't escape the trend root. Returns ``"_"``
    for an empty input.
    """
    return _SAFE_AGENT_RE.sub("_", name) or "_"


@dataclass(slots=True, frozen=True)
class RegressionAlert:
    """Structured payload for one regression alert."""

    kind: str  # "gate_regression" | "trend_decline"
    agent: str
    detail: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "agent": self.agent,
            "detail": self.detail,
            "extra": self.extra,
        }


class AlertSink(Protocol):
    def emit(self, alert: RegressionAlert) -> None: ...


@dataclass(slots=True)
class LogAlertSink:
    """Structured-log sink — the Phase-3 default, swappable for Slack
    / PagerDuty by satisfying the :class:`AlertSink` Protocol."""

    logger: Any | None = None

    def emit(self, alert: RegressionAlert) -> None:
        log = self.logger or structlog.get_logger("qaforge_eval.trend")
        log.warning("eval.regression_alert", **alert.to_dict())


@dataclass(slots=True)
class RegressionAlertEmitter:
    """Drive one nightly run's results into the trend store + alert
    sink. Idempotent over reruns: appending the same ``run_id`` twice
    creates two index entries (caller is responsible for run_id
    uniqueness if they care)."""

    store: TrendStore
    sink: AlertSink
    window: int = 3
    decline_threshold: float = 0.05

    def consume(self, *, run_id: str, report: NightlyReport) -> list[RegressionAlert]:
        alerts: list[RegressionAlert] = []
        for result in report.results:
            entry = TrendEntry(
                agent=result.agent,
                run_id=run_id,
                finished_at=report.finished_at,
                overall_pass_rate=result.scorecard.overall_pass_rate,
                has_regressions=result.has_regressions,
            )
            self.store.append(entry, payload=result.to_dict())

            if result.has_regressions:
                alerts.append(self._gate_alert(result))

            decline = self._detect_decline(agent=result.agent)
            if decline is not None:
                alerts.append(decline)

        for alert in alerts:
            self.sink.emit(alert)
        return alerts

    def _gate_alert(self, result: NightlyAgentResult) -> RegressionAlert:
        regressions = result.gate_report.regressions if result.gate_report else ()
        return RegressionAlert(
            kind="gate_regression",
            agent=result.agent,
            detail=(f"{len(regressions)} dimension(s) regressed past tolerance"),
            extra={
                "regressions": [
                    {
                        "dimension": f.dimension,
                        "metric": f.metric,
                        "delta": f.delta,
                    }
                    for f in regressions
                ],
                "overall_pass_rate": result.scorecard.overall_pass_rate,
            },
        )

    def _detect_decline(self, *, agent: str) -> RegressionAlert | None:
        history = self.store.history(agent=agent, limit=self.window)
        if len(history) < self.window:
            return None
        rates = [h.overall_pass_rate for h in history]
        if not _is_strictly_decreasing(rates):
            return None
        drop = rates[0] - rates[-1]
        if drop < self.decline_threshold:
            return None
        return RegressionAlert(
            kind="trend_decline",
            agent=agent,
            detail=(
                f"overall_pass_rate dropped {drop:.2%} over the last "
                f"{self.window} runs ({rates[0]:.2%} -> {rates[-1]:.2%})"
            ),
            extra={
                "window": self.window,
                "rates": rates,
                "mean": statistics.fmean(rates),
            },
        )


def _is_strictly_decreasing(values: Iterable[float]) -> bool:
    last: float | None = None
    for v in values:
        if last is not None and v >= last:
            return False
        last = v
    return True


__all__ = [
    "AlertSink",
    "FilesystemTrendStore",
    "LogAlertSink",
    "RegressionAlert",
    "RegressionAlertEmitter",
    "TrendEntry",
    "TrendStore",
]
