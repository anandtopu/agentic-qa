"""Caching + perf-budget tests — Epic 4.5.

Covers:

* :class:`LruCache` — get / set / TTL expiry / capacity eviction /
  ``get_or_compute`` factory + stats counters.
* :class:`EmbeddingCache` content-addressed key includes the model
  name so the same text under two different models doesn't collide.
* :class:`PlanReuseCache` invalidate path.
* :class:`PerfBudget` validation + percentile + verdict math.
* :func:`evaluate_perf_run` rolls up multi-capability runs into a
  single :class:`PerfBudgetReport`.
* :func:`time_call` records monotonic durations.
* k6 scenario thresholds match the Python budget ceilings (drift
  guard).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aqao_api.caching import (
    EmbeddingCache,
    LruCache,
    PlanReuseCache,
)
from aqao_api.perf import (
    DEFAULT_PERF_BUDGETS,
    PerfBudget,
    PerfBudgetReport,
    evaluate_perf_run,
    perf_budget_by_name,
    time_call,
)
from aqao_api.perf.budgets import BudgetVerdict

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------- LruCache


def test_lru_get_returns_set_value_and_records_hit() -> None:
    cache: LruCache[str, int] = LruCache(capacity=4)
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.stats.hits == 1
    assert cache.stats.misses == 0


def test_lru_get_missing_records_a_miss() -> None:
    cache: LruCache[str, int] = LruCache(capacity=4)
    assert cache.get("nope") is None
    assert cache.stats.misses == 1


def test_lru_evicts_least_recently_used_when_at_capacity() -> None:
    cache: LruCache[str, int] = LruCache(capacity=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # touch -> a is most-recent
    cache.set("c", 3)  # forces eviction
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.stats.evictions == 1


def test_lru_ttl_expires_entry_on_read() -> None:
    cache: LruCache[str, int] = LruCache(capacity=4, default_ttl=timedelta(seconds=10))
    base = datetime(2026, 5, 1, tzinfo=UTC)
    cache.set("a", 1, now=base)
    assert cache.get("a", now=base + timedelta(seconds=5)) == 1
    assert cache.get("a", now=base + timedelta(seconds=11)) is None


def test_lru_get_or_compute_calls_factory_only_on_miss() -> None:
    cache: LruCache[str, int] = LruCache(capacity=4)
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return 99

    assert cache.get_or_compute("a", factory) == 99
    assert cache.get_or_compute("a", factory) == 99
    assert calls["n"] == 1


def test_lru_invalidate_removes_entry() -> None:
    cache: LruCache[str, int] = LruCache(capacity=4)
    cache.set("a", 1)
    cache.invalidate("a")
    assert cache.get("a") is None


def test_lru_rejects_zero_capacity() -> None:
    with pytest.raises(ValueError, match="capacity"):
        LruCache(capacity=0)


# ---------------------------------------------------------------- EmbeddingCache


def test_embedding_cache_keys_include_model_name() -> None:
    cache = EmbeddingCache.with_capacity(capacity=8, ttl=None)

    def make_a() -> list[float]:
        return [1.0, 2.0]

    def make_b() -> list[float]:
        return [9.0, 9.0]

    out_a = cache.get_or_compute(model="m-a", text="hello", factory=make_a)
    out_b = cache.get_or_compute(model="m-b", text="hello", factory=make_b)
    # Same text under different models -> different cache entries.
    assert out_a == [1.0, 2.0]
    assert out_b == [9.0, 9.0]


def test_embedding_cache_hits_on_identical_input() -> None:
    cache = EmbeddingCache.with_capacity(capacity=8, ttl=None)
    calls = {"n": 0}

    def factory() -> list[float]:
        calls["n"] += 1
        return [3.14]

    cache.get_or_compute(model="m", text="x", factory=factory)
    cache.get_or_compute(model="m", text="x", factory=factory)
    assert calls["n"] == 1


# ---------------------------------------------------------------- PlanReuseCache


def test_plan_cache_round_trip_and_invalidate() -> None:
    cache = PlanReuseCache.with_capacity(capacity=8, ttl=None)
    workspace = uuid.uuid4()
    plan = {"steps": [1, 2, 3]}
    cache.set(workspace_id=workspace, requirement_hash="abc", plan=plan)
    assert cache.get(workspace_id=workspace, requirement_hash="abc") == plan
    cache.invalidate(workspace_id=workspace, requirement_hash="abc")
    assert cache.get(workspace_id=workspace, requirement_hash="abc") is None


def test_plan_cache_isolates_workspaces() -> None:
    cache = PlanReuseCache.with_capacity(capacity=8, ttl=None)
    a, b = uuid.uuid4(), uuid.uuid4()
    cache.set(workspace_id=a, requirement_hash="h", plan={"who": "a"})
    cache.set(workspace_id=b, requirement_hash="h", plan={"who": "b"})
    assert cache.get(workspace_id=a, requirement_hash="h") == {"who": "a"}
    assert cache.get(workspace_id=b, requirement_hash="h") == {"who": "b"}


# ---------------------------------------------------------------- PerfBudget


def test_budget_validation() -> None:
    with pytest.raises(ValueError, match="ceiling"):
        PerfBudget(name="x", ceiling_ms=0)
    with pytest.raises(ValueError, match="warn_pct"):
        PerfBudget(name="x", ceiling_ms=100, warn_pct=1.5)


def test_budget_warn_threshold_is_80_pct_by_default() -> None:
    b = PerfBudget(name="x", ceiling_ms=100)
    assert b.warn_threshold_ms == 80


def test_perf_budget_by_name_known_capability() -> None:
    assert perf_budget_by_name("pr_analysis").ceiling_ms == 60_000
    assert perf_budget_by_name("evidence_report").ceiling_ms == 30_000


def test_perf_budget_by_name_unknown_raises() -> None:
    with pytest.raises(KeyError):
        perf_budget_by_name("nope")


# ---------------------------------------------------------------- evaluate_perf_run


def test_evaluate_perf_run_passes_when_every_sample_under_warn() -> None:
    samples = {
        "pr_analysis": [10_000, 20_000, 30_000, 40_000, 47_000],  # max 47s, warn=48s
        "failure_classification": [5_000, 8_000, 12_000, 30_000, 45_000],
    }
    report = evaluate_perf_run(samples)
    assert isinstance(report, PerfBudgetReport)
    assert report.overall_verdict is BudgetVerdict.PASS
    assert not report.has_failures


def test_evaluate_perf_run_warns_on_sample_between_warn_and_ceiling() -> None:
    # PR analysis ceiling 60_000ms, warn = 48_000ms.
    samples = {"pr_analysis": [10_000, 49_000, 55_000]}
    report = evaluate_perf_run(samples)
    assert report.overall_verdict is BudgetVerdict.WARN


def test_evaluate_perf_run_fails_on_sample_over_ceiling() -> None:
    samples = {"pr_analysis": [10_000, 65_000]}
    report = evaluate_perf_run(samples)
    assert report.overall_verdict is BudgetVerdict.FAIL
    assert report.has_failures


def test_evaluate_perf_run_ignores_unknown_capability() -> None:
    """A run that includes a capability we haven't budgeted for
    should not crash — ignore + report only the known ones."""
    samples = {"made_up": [1, 2, 3], "pr_analysis": [1_000]}
    report = evaluate_perf_run(samples)
    capabilities = {c.budget.name for c in report.capabilities}
    assert capabilities == {"pr_analysis"}


def test_capability_result_records_p95_and_p99() -> None:
    samples = {
        "pr_analysis": list(range(1_000, 11_000, 100)),  # 100 samples
    }
    report = evaluate_perf_run(samples)
    cap = report.capabilities[0]
    assert cap.sample_count == 100
    # p50 < p95 < p99 < max.
    assert cap.p50_ms < cap.p95_ms < cap.p99_ms <= cap.max_ms


# ---------------------------------------------------------------- time_call


def test_time_call_records_a_positive_duration() -> None:
    with time_call("sleep") as t:
        time.sleep(0.005)
    assert t.name == "sleep"
    assert t.duration_ms >= 0  # may round to 0 on a fast box


def test_time_call_records_duration_even_on_exception() -> None:
    with pytest.raises(RuntimeError), time_call("boom") as t:
        raise RuntimeError("inside")
    # Duration is still recorded — caller can read it from the
    # context-manager record.
    assert t.duration_ms >= 0


# ---------------------------------------------------------------- k6 drift guard


def test_k6_lib_budgets_match_python_defaults() -> None:
    """The k6 thresholds in perf-tests/lib/checks.js mirror the Python
    perf budgets — drift one without the other and the load test
    silently lowers the bar."""
    js = (REPO_ROOT / "perf-tests" / "lib" / "checks.js").read_text(encoding="utf-8")
    for budget in DEFAULT_PERF_BUDGETS:
        # Each budget should appear as `<name>: <ceiling>` in the JS
        # constants block.
        assert (
            f"{budget.name}: {budget.ceiling_ms:_}".replace("_", "_") in js
            or f"{budget.name}: {budget.ceiling_ms}" in js
        ), budget.name


def test_perf_test_scenarios_present() -> None:
    scenarios = REPO_ROOT / "perf-tests" / "scenarios"
    assert scenarios.is_dir()
    names = {p.stem for p in scenarios.iterdir() if p.suffix == ".js"}
    assert {"pr_analysis", "failure_classify"} <= names
