"""Unit tests for the PR comment renderer — Story 1.9.2."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from aqao_agents.reporter import (
    FailureSummary,
    GoNoGo,
    PrCommentRenderer,
    RunReportContext,
)
from aqao_agents.reporter.pr_comment import PR_COMMENT_MARKER

_RUN_ID = UUID("11111111-2222-3333-4444-555555555555")
_PINNED_GENERATED_AT = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _ctx(**overrides: object) -> RunReportContext:
    base: dict[str, object] = {
        "workspace_name": "Payments",
        "test_run_id": _RUN_ID,
        "test_plan_summary": "Regression for PR #42",
        "state": "done",
        "started_at": None,
        "finished_at": None,
        "duration_ms": 0,
        "generated_at": _PINNED_GENERATED_AT,
        "recommendation": GoNoGo.GO,
        "recommendation_reasoning": "All checks passed.",
        "total": 5,
        "passed": 5,
        "failed": 0,
        "skipped": 0,
    }
    base.update(overrides)
    return RunReportContext.model_validate(base)


def test_marker_is_first_line() -> None:
    out = PrCommentRenderer().render(_ctx())
    assert out.splitlines()[0] == PR_COMMENT_MARKER


def test_recommendation_badge_present() -> None:
    out = PrCommentRenderer().render(_ctx(recommendation=GoNoGo.NO_GO))
    assert "❌ **NO GO**" in out


def test_no_failures_section_when_empty() -> None:
    out = PrCommentRenderer().render(_ctx())
    assert "<summary>Top failures</summary>" not in out


def test_top_failures_capped_at_three() -> None:
    failures = [
        FailureSummary(
            signal_id=f"s{i}",
            category="product_defect",
            confidence=Decimal("0.80"),
            classified_by="heuristic",
            rule="http_5xx",
            reasoning=f"failure {i}",
            suggested_fix=None,
        )
        for i in range(5)
    ]
    out = PrCommentRenderer().render(
        _ctx(state="failed", failed=5, failures=failures, recommendation=GoNoGo.NO_GO)
    )
    assert "s0" in out
    assert "s2" in out
    # Third index is the cap; 4 onwards collapses into "… N more"
    assert "… 2 more" in out


def test_signed_url_is_linked_when_provided() -> None:
    out = PrCommentRenderer().render(
        _ctx(),
        report_signed_url="https://signed.example/run.md",
        run_url="https://aqao.ai/runs/abc",
    )
    assert "[Full evidence report](https://signed.example/run.md)" in out
    assert "[Run details](https://aqao.ai/runs/abc)" in out


def test_render_is_deterministic_for_same_context() -> None:
    ctx = _ctx()
    renderer = PrCommentRenderer()
    assert renderer.render(ctx) == renderer.render(ctx)


def test_footer_includes_run_id() -> None:
    out = PrCommentRenderer().render(_ctx())
    assert str(_RUN_ID) in out


def test_collapsed_details_section_uses_html_details_tags() -> None:
    failures = [
        FailureSummary(
            signal_id="s1",
            category="test_issue",
            confidence=Decimal("0.70"),
            classified_by="llm",
            reasoning="brittle selector",
            suggested_fix="use getByTestId",
        )
    ]
    out = PrCommentRenderer().render(_ctx(failures=failures, failed=1))
    assert "<details>" in out
    assert "</details>" in out
    assert "use getByTestId" in out
