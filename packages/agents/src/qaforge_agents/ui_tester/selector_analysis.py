"""Selector fragility detector — Story 1.5.3.

Scans Playwright TS source for selector patterns that historically
produce flaky tests, and emits suggested replacements. The PRD AC
target is ≥60% recall on a gold set; the rules below cover the patterns
Playwright's own docs flag as anti-patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class FragilityFinding:
    line_number: int
    snippet: str
    rule: str
    severity: str  # "high" | "medium" | "low"
    suggestion: str


@dataclass(slots=True)
class FragilityReport:
    findings: list[FragilityFinding]

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.rule] = out.get(f.rule, 0) + 1
        return out


_RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "xpath_locator",
        re.compile(r"""(?P<m>['"`]\s*xpath\s*=)""", re.IGNORECASE),
        "high",
        "Replace XPath with page.getByRole / page.getByTestId / page.getByLabel.",
    ),
    (
        "xpath_double_slash",
        re.compile(r"""(?P<m>['"`]//[A-Za-z*])"""),
        "high",
        "XPath ``//element`` patterns are brittle — switch to a role/test-id locator.",
    ),
    (
        "deep_nth_child",
        re.compile(r"(?P<m>:nth-(?:child|of-type)\((\d+)\))"),
        "medium",
        "nth-child indices break on UI re-orderings — prefer getByTestId.",
    ),
    (
        "deep_descendant_chain",
        re.compile(r"(?P<m>(?:>\s*[a-zA-Z][\w*-]*\s*){4,})"),
        "medium",
        "Deep ``> el > el > ...`` chains are brittle — anchor on a stable testid.",
    ),
    (
        "class_selector",
        re.compile(r"""(?P<m>['"`]\.[A-Za-z][\w-]*['"`])"""),
        "low",
        "Class-based selectors break on CSS refactors — prefer data-testid.",
    ),
    (
        "text_with_id_suffix",
        re.compile(r"""(?P<m>getByText\(\s*['"`][^'"`]*\b\d{2,}\b[^'"`]*['"`])"""),
        "medium",
        "Text matching with embedded ids/numbers is unstable — match on the stable label.",
    ),
)


def analyse_selectors(source: str) -> FragilityReport:
    """Scan TS source line-by-line and return all matched fragility rules."""
    findings: list[FragilityFinding] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for rule, pattern, severity, suggestion in _RULES:
            for match in pattern.finditer(line):
                if rule == "deep_nth_child":
                    n = int(match.group(2))
                    if n <= 3:
                        continue
                findings.append(
                    FragilityFinding(
                        line_number=line_number,
                        snippet=line.strip(),
                        rule=rule,
                        severity=severity,
                        suggestion=suggestion,
                    )
                )
    return FragilityReport(findings=findings)
