"""PR comment renderer — Story 1.9.2.

A compact, scannable Markdown body suitable for a GitHub PR comment.
Includes a hidden HTML-comment marker (``QAFORGE_PR_COMMENT_MARKER``)
so the GitHub Action can find an existing QAForge comment and update
it in place rather than spamming a new one each push.
"""

from __future__ import annotations

from dataclasses import dataclass

from qaforge_agents.reporter.types import GoNoGo, RunReportContext

PR_COMMENT_MARKER = "<!-- qaforge:pr-comment:v1 -->"
"""HTML comment GitHub Actions look for to identify the QAForge comment."""

_BADGE: dict[GoNoGo, str] = {
    GoNoGo.GO: "✅ **GO**",
    GoNoGo.NO_GO: "❌ **NO GO**",
    GoNoGo.NEEDS_REVIEW: "🟡 **REVIEW**",
}

_TOP_FAILURES = 3


@dataclass(slots=True)
class PrCommentRenderer:
    """Renders a compact PR comment body.

    Kept template-free (string composition only) so a unit test can
    assert exact substrings without fighting Jinja whitespace rules.
    """

    template_version: str = "1.0.0"

    def render(
        self,
        context: RunReportContext,
        *,
        report_signed_url: str | None = None,
        run_url: str | None = None,
    ) -> str:
        lines: list[str] = []
        lines.append(PR_COMMENT_MARKER)
        lines.append("## QAForge AI — Run Summary")
        lines.append("")
        lines.append(
            f"{_BADGE[context.recommendation]}"
            f" — {context.recommendation_reasoning or '_no rationale provided_'}"
        )
        lines.append("")

        # Top-level stats
        lines.append(
            f"`{context.state}` · "
            f"{context.passed} passed · {context.failed} failed · "
            f"{context.skipped} skipped · "
            f"{len(context.failures)} classification(s)"
        )
        lines.append("")

        # Top failures
        if context.failures:
            lines.append("<details>")
            lines.append("<summary>Top failures</summary>")
            lines.append("")
            for failure in context.failures[:_TOP_FAILURES]:
                source = failure.classified_by
                rule = f", rule `{failure.rule}`" if failure.rule else ""
                lines.append(
                    f"- **`{failure.signal_id}`** — `{failure.category}` "
                    f"(via {source}{rule}, conf `{failure.confidence}`)"
                )
                lines.append(f"  {failure.reasoning}")
                if failure.suggested_fix:
                    lines.append(f"  _Fix:_ {failure.suggested_fix}")
            if len(context.failures) > _TOP_FAILURES:
                lines.append(
                    f"- _… {len(context.failures) - _TOP_FAILURES} more in the full report._"
                )
            lines.append("")
            lines.append("</details>")
            lines.append("")

        # Footer links
        footer_bits: list[str] = []
        if report_signed_url:
            footer_bits.append(f"[Full evidence report]({report_signed_url})")
        if run_url:
            footer_bits.append(f"[Run details]({run_url})")
        if footer_bits:
            lines.append(" · ".join(footer_bits))
            lines.append("")

        lines.append(
            f"<sub>QAForge run `{context.test_run_id}` · "
            f"template `{context.template_version}` · "
            f"comment `{self.template_version}`</sub>"
        )
        return "\n".join(lines).rstrip() + "\n"
