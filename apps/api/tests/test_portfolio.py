"""Portfolio deliverables smoke tests — Story 5.4.

Asserts every PRD §20 artifact exists at the expected path + the
README links the portfolio index. The Story 5.4 AC says all twelve
deliverables are checked into ``docs/portfolio/`` and linked from
README; this test enforces that contract so a future regression
fails loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PORTFOLIO_DIR = REPO_ROOT / "docs" / "portfolio"


# Deliverable -> filename. PRD §20 lists 12; the GitHub repo itself
# is item #1 and doesn't need a file under docs/portfolio/.
EXPECTED_DELIVERABLES = {
    "architecture": "architecture.md",
    "demo_video": "demo-video.md",
    "sample_app": "sample-app.md",
    "generated_test_plans": "generated-test-plans.md",
    "ci_runs": "ci-runs.md",
    "evidence_reports": "evidence-reports.md",
    "classification_examples": "classification-examples.md",
    "risk_dashboard": "risk-dashboard.md",
    "evaluation_report": "evaluation-report.md",
    "benchmarks": "benchmarks.md",
    "security_audit": "security-audit.md",
}


def _read(*parts: str) -> str:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8")


# ---------------------------------------------------------------- index


def test_portfolio_index_exists() -> None:
    assert (PORTFOLIO_DIR / "index.md").is_file()


def test_portfolio_index_links_every_deliverable() -> None:
    body = _read("docs", "portfolio", "index.md")
    for filename in EXPECTED_DELIVERABLES.values():
        assert filename in body, filename


def test_portfolio_index_lists_all_twelve_deliverables() -> None:
    """PRD §20 lists 12 deliverables. The index table should
    enumerate every one — the table rows are numbered ``| 1 | ... |``
    through ``| 12 | ... |``."""
    body = _read("docs", "portfolio", "index.md")
    for n in range(1, 13):
        assert f"| {n} |" in body, f"missing row {n}"


# ---------------------------------------------------------------- per-deliverable


@pytest.mark.parametrize("name,filename", sorted(EXPECTED_DELIVERABLES.items()))
def test_deliverable_file_exists(name: str, filename: str) -> None:
    path = PORTFOLIO_DIR / filename
    assert path.is_file(), f"{name} -> {path}"


@pytest.mark.parametrize("name,filename", sorted(EXPECTED_DELIVERABLES.items()))
def test_deliverable_file_is_non_empty(name: str, filename: str) -> None:
    body = (PORTFOLIO_DIR / filename).read_text(encoding="utf-8")
    # Each deliverable is at least a substantive page — not just a
    # placeholder. 800 chars filters out empty stubs.
    assert len(body) > 800, f"{name} ({filename}) only has {len(body)} chars"


# ---------------------------------------------------------------- cross-links


def test_architecture_doc_references_existing_diagrams_dir() -> None:
    body = _read("docs", "portfolio", "architecture.md")
    assert "docs/architecture" in body or "../architecture" in body


def test_security_audit_links_to_threat_model() -> None:
    body = _read("docs", "portfolio", "security-audit.md")
    assert "threat-model.md" in body


def test_evidence_reports_anchor_to_prd_section() -> None:
    body = _read("docs", "portfolio", "evidence-reports.md")
    # The PRD §9.11 sections are the spec the renderer hits.
    for section in ("Release summary", "Risk score", "Failure classification"):
        assert section in body, section


def test_risk_dashboard_lists_all_ten_inputs() -> None:
    body = _read("docs", "portfolio", "risk-dashboard.md")
    for signal in (
        "fail_rate",
        "critical_failures",
        "uncovered_acceptance",
        "flakiness",
        "change_volume",
        "historical_defect_density",
        "recent_incidents",
        "ownership_gap",
        "security_sensitivity",
        "untested_high_risk_modules",
    ):
        assert signal in body, signal


def test_classification_examples_cover_all_five_categories() -> None:
    body = _read("docs", "portfolio", "classification-examples.md")
    for category in (
        "product_defect",
        "test_issue",
        "environment_issue",
        "flaky_test",
        "data_issue",
    ):
        assert category in body, category


def test_benchmarks_lists_all_six_capability_budgets() -> None:
    body = _read("docs", "portfolio", "benchmarks.md")
    for capability in (
        "PR analysis",
        "Test plan generation",
        "API smoke",
        "UI smoke",
        "Failure classification",
        "Evidence report",
    ):
        assert capability in body, capability


# ---------------------------------------------------------------- README


def test_readme_links_to_portfolio_index() -> None:
    body = _read("README.md")
    assert "docs/portfolio/index.md" in body


def test_readme_lists_each_deliverable_link() -> None:
    """The README needs to expose the deliverables; portfolio index is
    a catalog but the README is what reviewers see first."""
    body = _read("README.md")
    # Spot-check three; full coverage is the index test above.
    assert "docs/portfolio/architecture.md" in body
    assert "docs/portfolio/risk-dashboard.md" in body
    assert "docs/portfolio/security-audit.md" in body
