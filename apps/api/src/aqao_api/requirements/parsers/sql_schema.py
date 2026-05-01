"""SQL DDL parser (regex-assisted balanced-paren scanner, dialect-agnostic).

Phase 1 MVP: extract ``CREATE TABLE`` statements with their columns. We
intentionally stay regex-only (no sqlparse dependency) so the parser is
predictable across dialects and small enough to unit-test exhaustively.
"""

from __future__ import annotations

import re
from typing import Any

from aqao_api.requirements.parsers.base import ParsedRequirement, ParseError

_CREATE_HEAD = re.compile(
    r"""
    \bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+
    (?:IF\s+NOT\s+EXISTS\s+)?
    (?P<name>
        `[^`]+`
      | "[^"]+"
      | \[[^\]]+\]
      | [\w.]+
    )
    \s*\(
    """,
    re.IGNORECASE | re.VERBOSE,
)
_COLUMN = re.compile(
    r"""
    ^\s*
    (?P<name>
        `[^`]+`
      | "[^"]+"
      | \[[^\]]+\]
      | \w+
    )
    \s+
    (?P<type>[A-Z][A-Z0-9_]*(?:\s*\([^)]*\))?)
    (?P<rest>.*)$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_CONSTRAINT_PREFIX = re.compile(
    r"^\s*(?:PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT)\b",
    re.IGNORECASE,
)


def parse(raw: dict[str, Any]) -> ParsedRequirement:
    body = raw.get("body") or raw.get("content") or raw.get("ddl")
    if not isinstance(body, str) or not body.strip():
        raise ParseError("SQL body is required", field="body")

    tables: list[dict[str, Any]] = []
    for match in _CREATE_HEAD.finditer(body):
        table_name = _strip_quotes(match.group("name"))
        body_text, _ = _read_balanced(body, match.end())
        if body_text is None:
            continue
        columns = _parse_columns(body_text)
        tables.append(
            {
                "name": table_name,
                "column_count": len(columns),
                "columns": columns,
            }
        )

    if not tables:
        raise ParseError("no CREATE TABLE statements found", field="body")

    return ParsedRequirement(
        summary=f"{len(tables)} table(s)",
        source_ref=raw.get("source_ref"),
        payload={"tables": tables},
    )


def _read_balanced(source: str, start: int) -> tuple[str | None, int]:
    """Return the substring up to the matching ``)`` (depth-aware)."""
    depth = 1
    i = start
    while i < len(source):
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return source[start:i], i
        i += 1
    return None, i


def _parse_columns(body: str) -> list[dict[str, Any]]:
    columns: list[dict[str, Any]] = []
    for line in _split_top_level_commas(body):
        if not line.strip() or _CONSTRAINT_PREFIX.match(line):
            continue
        m = _COLUMN.match(line.strip())
        if not m:
            continue
        rest = m.group("rest").upper()
        nullable = "NOT NULL" not in rest
        primary = "PRIMARY KEY" in rest
        columns.append(
            {
                "name": _strip_quotes(m.group("name")),
                "type": m.group("type").upper().rstrip(),
                "nullable": nullable,
                "primary_key": primary,
            }
        )
    return columns


def _split_top_level_commas(body: str) -> list[str]:
    """Split on commas that aren't inside parentheses."""
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _strip_quotes(name: str) -> str:
    return name.strip().strip('`"[]')
