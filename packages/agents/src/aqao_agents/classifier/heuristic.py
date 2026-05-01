"""Heuristic pre-classifier — Story 1.7.1.

Regex- and structure-driven rule pack. Each rule maps a recognisable
failure pattern to a :class:`FailureCategory` with a fixed confidence.
Rules are tried in order from most-specific to most-general; the first
match wins.

Story 1.7.1 AC target: ≥30% of failures classified pre-LLM. The rules
below cover the patterns most agents-under-test surface in practice:
network errors, 5xx, 4xx auth, selector-not-found, browser nav, Python
tracebacks, assertion failures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from aqao_agents.classifier.schema import (
    Classification,
    ClassificationSource,
    FailureCategory,
    FailureSignal,
)


@dataclass(frozen=True, slots=True)
class HeuristicMatch:
    rule: str
    category: FailureCategory
    confidence: Decimal
    reasoning: str
    suggested_fix: str | None = None


# Each entry: (rule_name, regex, category, confidence, reasoning, suggested_fix).
_TEXT_RULES: tuple[tuple[str, re.Pattern[str], FailureCategory, str, str, str | None], ...] = (
    (
        "network_timeout",
        re.compile(
            r"\b(ETIMEDOUT|ECONNRESET|connection\s+timed?\s*out|read\s+timeout|"
            r"timeout\s+exceeded)\b",
            re.IGNORECASE,
        ),
        FailureCategory.ENVIRONMENT_ISSUE,
        "0.85",
        "Network/transport timeout — typically environment-flaky.",
        "Retry with backoff; verify the target service's reachability from the runner network.",
    ),
    (
        "dns_resolution",
        re.compile(
            r"\b(ENOTFOUND|EAI_AGAIN|getaddrinfo|net::ERR_NAME_NOT_RESOLVED)\b",
            re.IGNORECASE,
        ),
        FailureCategory.ENVIRONMENT_ISSUE,
        "0.90",
        "DNS resolution failed — the target hostname could not be looked up.",
        "Check DNS, VPN, or hostname spelling in the test config.",
    ),
    (
        "browser_nav_error",
        re.compile(r"\bnet::ERR_[A-Z_]+", re.IGNORECASE),
        FailureCategory.ENVIRONMENT_ISSUE,
        "0.80",
        "Browser-level navigation error.",
        "Verify base URL + that the staging deployment is reachable.",
    ),
    (
        "selector_not_found",
        re.compile(
            r"\b(no\s+(?:element|node)\s+(?:found|matched)|element\s+not\s+visible|"
            r"selector\s+resolved\s+to\s+0\s+elements|locator\.click.*timed?\s*out|"
            r"strict\s+mode\s+violation)\b",
            re.IGNORECASE,
        ),
        FailureCategory.TEST_ISSUE,
        "0.75",
        "Playwright selector did not resolve to an element.",
        "Switch to getByRole / getByTestId; fragile selectors flagged by Story 1.5.3 analyzer.",
    ),
    (
        "assertion_failure",
        re.compile(
            r"\b(AssertionError|expect\([^\)]*\)\.[a-zA-Z]+\(.*?\)\s+failed|"
            r"assertion\s+failed)\b",
            re.IGNORECASE,
        ),
        FailureCategory.PRODUCT_DEFECT,
        "0.55",
        "An assertion failed — the system-under-test produced an "
        "unexpected response. Confirm against the spec before filing.",
        None,
    ),
    (
        "python_traceback",
        re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE),
        FailureCategory.UNKNOWN,
        "0.40",
        "Python traceback present — needs LLM follow-up to locate root cause.",
        None,
    ),
    (
        "rate_limited",
        re.compile(r"\b(429|rate\s+limit(?:ed)?|too\s+many\s+requests)\b", re.IGNORECASE),
        FailureCategory.ENVIRONMENT_ISSUE,
        "0.85",
        "Upstream rate-limited the runner.",
        "Add retry-with-backoff and/or a workspace-level rate budget.",
    ),
    (
        "missing_fixture",
        re.compile(
            r"\b(fixture\s+'?[A-Za-z_][\w-]*'?\s+not\s+found|"
            r"no\s+such\s+fixture|integrity(?:Error)?\s+constraint)\b",
            re.IGNORECASE,
        ),
        FailureCategory.DATA_ISSUE,
        "0.70",
        "Test depends on data/fixtures that were absent.",
        "Seed required rows or use the test_data agent's prep step.",
    ),
)


# Story 3.3.2 — flip-rate at or above this threshold is treated as
# meaningfully flaky. At 0.30 a third of recent paired runs flipped
# verdicts, which is far outside what a stable test produces.
FLAKINESS_FLIP_THRESHOLD = 0.30


@dataclass(slots=True)
class HeuristicClassifier:
    """Stateful classifier — pure-Python, no I/O."""

    flakiness_threshold: float = FLAKINESS_FLIP_THRESHOLD

    def classify(self, signal: FailureSignal) -> HeuristicMatch | None:
        text_match = self._classify_text(signal)
        return self._apply_flakiness(signal, text_match)

    def _apply_flakiness(
        self,
        signal: FailureSignal,
        match: HeuristicMatch | None,
    ) -> HeuristicMatch | None:
        """Story 3.3.2 — if the test has been flapping in recent runs,
        prefer ``FLAKY_TEST`` over ``PRODUCT_DEFECT``. Other categories
        (environment / data / test_issue) stay — those are legitimate
        non-product causes a flaky verdict can't override.
        """
        score = signal.flakiness_score
        if score is None or score < self.flakiness_threshold:
            return match

        confidence = Decimal(str(round(min(0.5 + score / 2, 0.95), 2)))
        if match is None:
            return HeuristicMatch(
                rule="flakiness_observed",
                category=FailureCategory.FLAKY_TEST,
                confidence=confidence,
                reasoning=(
                    f"14-day flip-rate {score:.0%} exceeds the "
                    f"{self.flakiness_threshold:.0%} flakiness threshold; "
                    "no other rule matched."
                ),
                suggested_fix=(
                    "Quarantine + investigate the test for race conditions "
                    "before treating the failure as a product defect."
                ),
            )
        if match.category is FailureCategory.PRODUCT_DEFECT:
            return HeuristicMatch(
                rule=f"{match.rule}+flakiness_override",
                category=FailureCategory.FLAKY_TEST,
                confidence=confidence,
                reasoning=(
                    f"Original rule matched ({match.rule}) but the test's "
                    f"14-day flip-rate is {score:.0%} — flakiness explains "
                    "the failure better than a product defect would."
                ),
                suggested_fix=(
                    "Re-run before opening a defect; if the verdict flips, treat as flake."
                ),
            )
        return match

    def _classify_text(self, signal: FailureSignal) -> HeuristicMatch | None:
        # Status-code rules first — most reliable signal.
        if signal.http_status_code is not None:
            if 500 <= signal.http_status_code < 600:
                return HeuristicMatch(
                    rule="http_5xx",
                    category=FailureCategory.PRODUCT_DEFECT,
                    confidence=Decimal("0.80"),
                    reasoning=(
                        f"HTTP {signal.http_status_code} from the system-under-test "
                        f"indicates a server-side error."
                    ),
                    suggested_fix=(
                        "Inspect the server logs at the failure timestamp; "
                        "check recent deploys for regressions."
                    ),
                )
            if signal.http_status_code in (401, 403):
                return HeuristicMatch(
                    rule="http_4xx_auth",
                    category=FailureCategory.ENVIRONMENT_ISSUE,
                    confidence=Decimal("0.85"),
                    reasoning=(
                        f"HTTP {signal.http_status_code} usually indicates an "
                        f"expired/missing credential rather than a product bug."
                    ),
                    suggested_fix=(
                        "Refresh the workspace's credential bundle (aqao_tools.credentials)."
                    ),
                )
            if signal.http_status_code in (408, 504):
                return HeuristicMatch(
                    rule="http_timeout_status",
                    category=FailureCategory.ENVIRONMENT_ISSUE,
                    confidence=Decimal("0.80"),
                    reasoning=(f"HTTP {signal.http_status_code} is a transport-level timeout."),
                    suggested_fix="Retry with backoff; check upstream latency.",
                )

        text = signal.composite_text
        if not text:
            return None

        for rule_name, pattern, category, conf, reasoning, fix in _TEXT_RULES:
            if pattern.search(text):
                return HeuristicMatch(
                    rule=rule_name,
                    category=category,
                    confidence=Decimal(conf),
                    reasoning=reasoning,
                    suggested_fix=fix,
                )
        return None

    def classify_to_classification(self, signal: FailureSignal) -> Classification | None:
        match = self.classify(signal)
        if match is None:
            return None
        return Classification(
            signal_id=signal.signal_id,
            category=match.category,
            confidence=match.confidence,
            classified_by=ClassificationSource.HEURISTIC,
            rule=match.rule,
            reasoning=match.reasoning,
            suggested_fix=match.suggested_fix,
        )
