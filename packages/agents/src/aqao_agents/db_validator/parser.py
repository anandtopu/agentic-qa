"""SQL statement classifier — Story 2.2.3.

Tags a SQL string as read-only or destructive. The classifier is
deliberately conservative: anything it cannot confidently identify as
read-only is treated as destructive so the approval gate fires.

Multi-statement scripts are split on top-level semicolons (string
literals + line/block comments are stripped first) and every
statement must be classified before the script as a whole is allowed
to bypass the gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

READ_ONLY_VERBS: frozenset[str] = frozenset(
    {
        "SELECT",
        "EXPLAIN",
        "SHOW",
        "WITH",  # CTEs — re-checked below to ensure body is SELECT-shaped
        "VALUES",
    }
)

DESTRUCTIVE_VERBS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
        "REINDEX",
        "VACUUM",
        "CALL",
        "EXEC",
        "EXECUTE",
    }
)


class SqlStatementKind(StrEnum):
    READ_ONLY = "read_only"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class SqlStatement:
    raw: str
    leading_verb: str
    kind: SqlStatementKind
    reason: str

    @property
    def is_destructive(self) -> bool:
        # UNKNOWN is treated as destructive at the gate boundary.
        return self.kind is not SqlStatementKind.READ_ONLY


@dataclass(slots=True)
class SqlStatementClassifier:
    """Classifies one or more SQL statements.

    Splits on top-level semicolons after stripping string literals and
    SQL comments so a ``DROP`` hidden inside a ``--`` comment doesn't
    falsely trip the gate. The scanner is small + bug-minded rather
    than a full parser — that's intentional: the consequence of a false
    positive is "needs human approval", which is fine.
    """

    extra_destructive_verbs: tuple[str, ...] = field(default_factory=tuple)

    def classify(self, sql: str) -> list[SqlStatement]:
        statements: list[SqlStatement] = []
        for raw in _split_statements(sql):
            cleaned = _strip_strings_and_comments(raw).strip()
            if not cleaned:
                continue
            statement = self._classify_one(raw=raw.strip(), cleaned=cleaned)
            statements.append(statement)
        return statements

    def is_script_destructive(self, sql: str) -> bool:
        """Convenience: True if any statement in the script is not
        confidently read-only."""
        return any(s.is_destructive for s in self.classify(sql))

    def _classify_one(self, *, raw: str, cleaned: str) -> SqlStatement:
        verb = _leading_verb(cleaned)
        destructive = DESTRUCTIVE_VERBS | {v.upper() for v in self.extra_destructive_verbs}
        if verb in destructive:
            return SqlStatement(
                raw=raw,
                leading_verb=verb,
                kind=SqlStatementKind.DESTRUCTIVE,
                reason=f"leading verb {verb!r} is on the destructive list",
            )
        if verb == "WITH":
            # WITH ... SELECT is read-only; WITH ... INSERT/UPDATE/DELETE
            # is destructive. Pick out the verb that follows the closing
            # paren of the CTE definition.
            inner_verb = _verb_after_with(cleaned)
            if inner_verb in destructive:
                return SqlStatement(
                    raw=raw,
                    leading_verb="WITH",
                    kind=SqlStatementKind.DESTRUCTIVE,
                    reason=(f"WITH-clause body uses destructive verb {inner_verb!r}"),
                )
            if inner_verb in READ_ONLY_VERBS:
                return SqlStatement(
                    raw=raw,
                    leading_verb="WITH",
                    kind=SqlStatementKind.READ_ONLY,
                    reason=f"WITH-clause body is {inner_verb!r}",
                )
            return SqlStatement(
                raw=raw,
                leading_verb="WITH",
                kind=SqlStatementKind.UNKNOWN,
                reason="WITH-clause body verb could not be determined",
            )
        if verb in READ_ONLY_VERBS:
            return SqlStatement(
                raw=raw,
                leading_verb=verb,
                kind=SqlStatementKind.READ_ONLY,
                reason=f"leading verb {verb!r} is read-only",
            )
        return SqlStatement(
            raw=raw,
            leading_verb=verb or "",
            kind=SqlStatementKind.UNKNOWN,
            reason=(
                f"leading verb {verb!r} is not on the read-only list — "
                "treating as destructive at the gate boundary"
            ),
        )


def classify_sql(sql: str) -> list[SqlStatement]:
    """Module-level convenience wrapping the default classifier."""
    return SqlStatementClassifier().classify(sql)


# ---------------------------------------------------------------------------- helpers


_LEADING_VERB_RE = re.compile(r"^\s*([A-Za-z]+)")


def _leading_verb(sql: str) -> str:
    match = _LEADING_VERB_RE.match(sql)
    return match.group(1).upper() if match else ""


def _verb_after_with(sql: str) -> str:
    """Find the verb that follows the closing paren of a top-level
    ``WITH name AS (...)`` clause. Returns "" if the parens never
    balance — caller treats that as UNKNOWN."""
    if not sql[:5].upper().startswith("WITH"):
        return ""
    i = 4  # skip past "WITH"
    n = len(sql)
    depth = 0
    saw_open = False
    while i < n:
        ch = sql[i]
        if ch == "(":
            depth += 1
            saw_open = True
        elif ch == ")":
            depth -= 1
            if depth == 0 and saw_open:
                # Look at what follows the closing paren.
                tail = sql[i + 1 :].lstrip()
                if tail.startswith(","):
                    # Multi-CTE — reset and keep scanning past the comma.
                    saw_open = False
                    i += 1
                    while i < n and sql[i] != ",":
                        i += 1
                    i += 1  # consume the comma
                    continue
                return _leading_verb(tail)
        i += 1
    return ""


_STRING_RE = re.compile(r"'([^'\\]|\\.|'')*'")
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_strings_and_comments(sql: str) -> str:
    """Replace string literals and SQL comments with spaces so the
    statement-splitter and verb scanner don't trip on them."""
    out = _BLOCK_COMMENT_RE.sub(" ", sql)
    out = _LINE_COMMENT_RE.sub(" ", out)
    return _STRING_RE.sub(" '_' ", out)


def _split_statements(sql: str) -> list[str]:
    """Split SQL on top-level semicolons. The cleaner has already
    stripped string literals + comments, so a raw ``;`` here is safe
    to treat as a statement terminator."""
    cleaned = _strip_strings_and_comments(sql)
    if ";" not in cleaned:
        return [sql]
    statements: list[str] = []
    buf: list[str] = []
    raw_idx = 0
    for ch in cleaned:
        if ch == ";":
            statements.append(sql[raw_idx : raw_idx + len(buf)])
            raw_idx += len(buf) + 1  # consume the semicolon
            buf = []
        else:
            buf.append(ch)
    tail = sql[raw_idx:]
    if tail.strip():
        statements.append(tail)
    return statements


__all__ = [
    "DESTRUCTIVE_VERBS",
    "READ_ONLY_VERBS",
    "SqlStatement",
    "SqlStatementClassifier",
    "SqlStatementKind",
    "classify_sql",
]
