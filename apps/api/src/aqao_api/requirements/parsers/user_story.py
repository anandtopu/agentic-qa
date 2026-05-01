"""Markdown user-story parser.

Extracts acceptance criteria from common author conventions:

* ``Given X, When Y, Then Z`` Gherkin lines.
* ``## Acceptance Criteria`` (or ``## AC``, ``## Acceptance criteria``)
  followed by a bulleted list (``-``, ``*``, ``- [ ]``, ``- [x]``).

Story 1.2.2 AC: 95% extraction accuracy on a 50-item gold set. Phase 1
ships the parser; the gold set is curated under
``packages/eval/datasets/user_story/``.
"""

from __future__ import annotations

import re
from typing import Any

from aqao_api.requirements.parsers.base import ParsedRequirement, ParseError

_AC_HEADING = re.compile(
    r"^\s{0,3}#{2,6}\s*(acceptance\s*criteria|ac|requirements)\s*$",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_GIVEN_WHEN_THEN = re.compile(r"^\s*(given|when|then|and|but)\s+(.+?)\s*$", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_TITLE_HEADING = re.compile(r"^\s{0,3}#\s+(.+?)\s*$")


def parse(raw: dict[str, Any]) -> ParsedRequirement:
    body = raw.get("body") or raw.get("markdown") or raw.get("content")
    if not isinstance(body, str) or not body.strip():
        raise ParseError("user story body is required", field="body")

    title = (raw.get("title") or "").strip() or _extract_title(body)
    acceptance_criteria = _extract_acceptance_criteria(body)
    gherkin = _extract_gherkin(body)

    if not acceptance_criteria and not gherkin:
        raise ParseError(
            "no acceptance criteria found — expected '## Acceptance Criteria' "
            "with bullets, or Given/When/Then lines",
            field="body",
        )

    summary = title or (
        acceptance_criteria[0]["text"] if acceptance_criteria else gherkin[0]["text"]
    )
    return ParsedRequirement(
        summary=summary,
        source_ref=raw.get("source_ref"),
        payload={
            "title": title,
            "body": body,
            "acceptance_criteria": acceptance_criteria,
            "gherkin": gherkin,
        },
    )


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        match = _TITLE_HEADING.match(line)
        if match:
            return match.group(1).strip()
    return ""


def _extract_acceptance_criteria(body: str) -> list[dict[str, Any]]:
    """Return a list of ``{text, checked}`` dicts under any AC heading."""
    out: list[dict[str, Any]] = []
    in_section = False
    lines = body.splitlines()
    for line in lines:
        if _AC_HEADING.match(line):
            in_section = True
            continue
        if in_section and _HEADING.match(line):
            in_section = False
            continue
        if not in_section:
            continue
        m = _BULLET.match(line)
        if m:
            text = m.group(1).strip()
            checked = "[x]" in line.lower() or "[X]" in line
            out.append({"text": text, "checked": checked})
    return out


def _extract_gherkin(body: str) -> list[dict[str, Any]]:
    """Return a list of ``{keyword, text}`` for Given/When/Then/And/But lines."""
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        m = _GIVEN_WHEN_THEN.match(line)
        if m:
            out.append({"keyword": m.group(1).lower(), "text": m.group(2).strip()})
    return out
