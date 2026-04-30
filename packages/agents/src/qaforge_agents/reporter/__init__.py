"""Evidence report renderer — Story 1.8.1.

Pure Jinja2 over a typed Pydantic context. The Reporter is not an
LLM — it's deterministic templating so reports across identical inputs
are byte-identical, which is what makes Story 1.8.1 snapshot-testable.

Structure mirrors PRD §9.11 sections: release summary, scope, coverage,
pass/fail, failure classification, risk, evidence, agent confidence,
cost / latency, human approvals, go/no-go recommendation.
"""

from qaforge_agents.reporter.pr_comment import (
    PR_COMMENT_MARKER,
    PrCommentRenderer,
)
from qaforge_agents.reporter.renderer import MarkdownReportRenderer
from qaforge_agents.reporter.types import (
    AgentTraceLine,
    ArtifactSummary,
    CoverageArea,
    FailureSummary,
    GoNoGo,
    RunReportContext,
    TestCaseSummary,
)

__all__ = [
    "PR_COMMENT_MARKER",
    "AgentTraceLine",
    "ArtifactSummary",
    "CoverageArea",
    "FailureSummary",
    "GoNoGo",
    "MarkdownReportRenderer",
    "PrCommentRenderer",
    "RunReportContext",
    "TestCaseSummary",
]
