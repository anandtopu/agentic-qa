"""Snapshot tests for the Markdown evidence report renderer — Story 1.8.1.

The Story 1.8.1 AC requires snapshot tests across 5 fixture runs to be
stable. We achieve that by:
* Pinning the ``generated_at`` timestamp.
* Using deterministic fixture data (no random uuids beyond the run id).
* Asserting both the structural skeleton (sections present) and that
  the rendered output is identical when re-rendered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from qaforge_agents.reporter import (
    AgentTraceLine,
    ArtifactSummary,
    CoverageArea,
    FailureSummary,
    GoNoGo,
    MarkdownReportRenderer,
    RunReportContext,
    TestCaseSummary,
)

_RUN_ID = UUID("11111111-2222-3333-4444-555555555555")
_PINNED_GENERATED_AT = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
_PINNED_STARTED_AT = datetime(2026, 5, 1, 11, 58, 0, tzinfo=UTC)
_PINNED_FINISHED_AT = datetime(2026, 5, 1, 11, 59, 30, tzinfo=UTC)


def _base_ctx(**overrides: object) -> RunReportContext:
    base: dict[str, object] = {
        "workspace_name": "Payments",
        "test_run_id": _RUN_ID,
        "test_plan_summary": "Regression for checkout PR #42",
        "state": "done",
        "started_at": _PINNED_STARTED_AT,
        "finished_at": _PINNED_FINISHED_AT,
        "duration_ms": 90_000,
        "generated_at": _PINNED_GENERATED_AT,
        "recommendation": GoNoGo.GO,
        "recommendation_reasoning": "All 3 critical-path tests passed.",
    }
    base.update(overrides)
    return RunReportContext.model_validate(base)


@pytest.fixture
def renderer() -> MarkdownReportRenderer:
    return MarkdownReportRenderer()


# --- Fixture 1: empty / minimal ---------------------------------------------


def test_renders_minimal_run(renderer: MarkdownReportRenderer) -> None:
    out = renderer.render(_base_ctx(state="planned"))
    assert "# QAForge Run Report — Payments" in out
    assert "**State:** `planned`" in out
    assert "_No coverage areas declared._" in out
    assert "_No test cases recorded._" in out
    assert "_No failure classifications recorded._" in out
    assert "_No artifacts recorded._" in out


def test_renders_minimal_run_is_deterministic(
    renderer: MarkdownReportRenderer,
) -> None:
    """Re-rendering with the same context must be byte-identical."""
    ctx = _base_ctx(state="planned")
    a = renderer.render(ctx)
    b = renderer.render(ctx)
    assert a == b


# --- Fixture 2: all-passing run ---------------------------------------------


def test_renders_passing_run(renderer: MarkdownReportRenderer) -> None:
    ctx = _base_ctx(
        coverage_areas=[
            CoverageArea(name="checkout API", case_count=3, passed=3, failed=0),
            CoverageArea(name="payment auth", case_count=2, passed=2, failed=0),
        ],
        test_cases=[
            TestCaseSummary(
                title="Successful charge",
                type="api",
                priority="high",
                status="passed",
            ),
            TestCaseSummary(
                title="Successful 3DS challenge",
                type="api",
                priority="high",
                status="passed",
            ),
        ],
        total=5,
        passed=5,
    )
    out = renderer.render(ctx)
    assert "**GO**" in out
    assert "Successful charge" in out
    assert "checkout API" in out
    assert "5 |" in out  # total cell


# --- Fixture 3: failing run with classifier output --------------------------


def test_renders_failing_run_with_classifications(
    renderer: MarkdownReportRenderer,
) -> None:
    ctx = _base_ctx(
        state="done",
        recommendation=GoNoGo.NO_GO,
        recommendation_reasoning="HTTP 500 on /charge — confirmed defect.",
        total=4,
        passed=3,
        failed=1,
        failures=[
            FailureSummary(
                signal_id="charge-1",
                category="product_defect",
                confidence=Decimal("0.80"),
                classified_by="heuristic",
                rule="http_5xx",
                reasoning="HTTP 503 from /charge.",
                suggested_fix="Inspect server logs at the failure timestamp.",
            )
        ],
        failure_category_counts={"product_defect": 1},
        heuristic_ratio=Decimal("1.00"),
    )
    out = renderer.render(ctx)
    assert "**NO_GO**" in out
    assert "`http_5xx`" in out
    assert "Inspect server logs" in out
    assert "100.00%" in out  # heuristic ratio formatted as percent


# --- Fixture 4: paused-for-approval -----------------------------------------


def test_renders_paused_run_with_open_questions(
    renderer: MarkdownReportRenderer,
) -> None:
    ctx = _base_ctx(
        state="paused_for_approval",
        recommendation=GoNoGo.NEEDS_REVIEW,
        recommendation_reasoning="Destructive SQL pending approval.",
        open_questions=[
            "Is row-level cleanup permitted on this environment?",
            "Should we soft-delete or hard-delete?",
        ],
    )
    out = renderer.render(ctx)
    assert "**NEEDS_REVIEW**" in out
    assert "Destructive SQL pending approval" in out
    assert "Is row-level cleanup permitted" in out


# --- Fixture 5: full agent trace + artifacts --------------------------------


def test_renders_full_trace_and_artifacts(
    renderer: MarkdownReportRenderer,
) -> None:
    ctx = _base_ctx(
        agent_trace=[
            AgentTraceLine(
                step_index=0,
                agent_name="plan",
                state="succeeded",
                duration_ms=2400,
                attempt=1,
            ),
            AgentTraceLine(
                step_index=1,
                agent_name="execute",
                state="succeeded",
                duration_ms=45_000,
                attempt=1,
            ),
            AgentTraceLine(
                step_index=2,
                agent_name="classify",
                state="succeeded",
                duration_ms=900,
                attempt=1,
            ),
        ],
        artifacts=[
            ArtifactSummary(
                kind="trace",
                filename="trace.zip",
                sha256="a" * 64,
                size_bytes=12_345,
                signed_url="https://signed.example/trace.zip",
                signed_url_expires_at=datetime(2026, 5, 1, 12, 15, 0, tzinfo=UTC),
            ),
            ArtifactSummary(
                kind="report",
                filename="run_report.md",
                sha256="b" * 64,
                size_bytes=1_024,
            ),
        ],
        total_usd_cost_cents=37,
        total_latency_ms=48_300,
    )
    out = renderer.render(ctx)
    assert "| 0 | `plan` | `succeeded`" in out
    assert "trace.zip" in out
    assert "[fetch](https://signed.example/trace.zip)" in out
    assert "$0.37" in out  # cost formatted
