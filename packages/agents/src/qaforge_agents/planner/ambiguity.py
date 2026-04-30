"""Heuristic open-question detector — Story 1.3.2.

Layered on top of the LLM's own ``open_questions`` list. The aim is to
catch easy classes of ambiguity the model commonly misses; the LLM still
owns the harder semantic gaps.
"""

from __future__ import annotations

import re
from typing import Any

_VAGUE_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bsomehow\b", re.IGNORECASE),
        'Word "somehow" is vague — what mechanism is required?',
    ),
    (
        re.compile(r"\b(reasonable|appropriate|suitable)\b", re.IGNORECASE),
        "Subjective qualifier present — define a measurable threshold.",
    ),
    (
        re.compile(r"\b(fast|quickly|slow)\b", re.IGNORECASE),
        "Performance qualifier present — specify a numeric latency budget.",
    ),
    (
        re.compile(r"\bsupport(s|ed)?\b", re.IGNORECASE),
        '"Support" is broad — list the exact behaviours required.',
    ),
    (
        re.compile(r"\b(if needed|as required|where applicable)\b", re.IGNORECASE),
        "Conditional qualifier — under exactly which conditions?",
    ),
    (
        re.compile(r"\b(handle|deal with)\b", re.IGNORECASE),
        '"Handle" is vague — what is the expected outcome on success/failure?',
    ),
)

_NEGATIVE_KEYWORDS = (
    "invalid",
    "error",
    "fail",
    "denied",
    "unauthor",
    "forbidden",
    "timeout",
    "rate limit",
)


def detect_open_questions(
    *,
    requirement_summary: str,
    parsed_payload: dict[str, Any],
    test_cases: list[dict[str, Any]],
) -> list[str]:
    """Return a list of additional open questions inferred heuristically."""
    out: list[str] = []
    text_blob = _flatten_strings(parsed_payload) + " " + requirement_summary

    for pattern, message in _VAGUE_PHRASES:
        if pattern.search(text_blob):
            out.append(message)

    if not _has_negative_path(test_cases):
        out.append(
            "No negative or error-path test case present — at least one is "
            "expected unless explicitly out of scope."
        )

    if _references_auth(text_blob) and not _has_auth_failure_case(test_cases):
        out.append(
            "Requirement references authentication but no authn-failure test case is included."
        )

    return out


def _flatten_strings(payload: object) -> str:
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for entry in node:
                walk(entry)

    walk(payload)
    return " ".join(out)


def _has_negative_path(test_cases: list[dict[str, Any]]) -> bool:
    for case in test_cases:
        if str(case.get("type", "")).lower() in {"negative", "integration"}:
            return True
        title = str(case.get("title", "")).lower()
        expected = str(case.get("expected_result", "")).lower()
        if any(kw in title or kw in expected for kw in _NEGATIVE_KEYWORDS):
            return True
    return False


def _references_auth(text_blob: str) -> bool:
    blob = text_blob.lower()
    return any(
        token in blob for token in ("login", "logout", "auth", "session", "password", "oauth")
    )


def _has_auth_failure_case(test_cases: list[dict[str, Any]]) -> bool:
    for case in test_cases:
        title = str(case.get("title", "")).lower()
        expected = str(case.get("expected_result", "")).lower()
        if "auth" in title or "auth" in expected:
            if "fail" in title or "fail" in expected or "denied" in expected:
                return True
            if "401" in expected or "403" in expected:
                return True
    return False
