"""Read-only DB validators — Story 2.2.1.

Each :class:`Validator` runs a small set of SELECT-only queries against
the tested database and surfaces findings (orphan rows, NULLs in
NOT-NULL-expected columns, etc.) without ever issuing a write.

The :class:`DbConnection` Protocol keeps this module decoupled from
SQLAlchemy specifics — tests pass a stub, production wires a real
``Connection.execute_many`` adapter.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class Finding:
    """One issue surfaced by a validator."""

    rule: str
    severity: Severity
    detail: str
    table: str | None = None
    column: str | None = None
    row_count: int = 0
    sample_row_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "detail": self.detail,
            "table": self.table,
            "column": self.column,
            "row_count": self.row_count,
            "sample_row_ids": list(self.sample_row_ids),
        }


class DbConnection(Protocol):
    """Read-only SQL surface a Validator needs.

    Production implementations wrap a SQLAlchemy ``Connection`` with
    ``execute()`` returning an iterable of mappings. The Protocol does
    not commit, rollback, or expose mutating verbs — validators are
    closed under SELECT.
    """

    def execute(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> Iterable[dict[str, Any]]: ...


class Validator(Protocol):
    name: str

    def check(self, conn: DbConnection) -> list[Finding]: ...


@dataclass(slots=True)
class ForeignKeyOrphanValidator:
    """Find rows in ``child_table.fk_column`` whose value does not exist
    in ``parent_table.parent_pk``.

    Emits a single ``error`` finding when orphans are detected, with
    the first ``sample_limit`` row ids for triage.
    """

    child_table: str
    fk_column: str
    parent_table: str
    parent_pk: str = "id"
    child_pk: str = "id"
    sample_limit: int = 10
    name: str = "foreign_key_orphan"

    def check(self, conn: DbConnection) -> list[Finding]:
        # Identifiers come from trusted validator config, not user input;
        # parameterised queries can't bind table/column names anyway.
        sql = (
            f"SELECT c.{self.child_pk} AS rid "  # noqa: S608
            f"FROM {self.child_table} c "
            f"LEFT JOIN {self.parent_table} p "
            f"  ON c.{self.fk_column} = p.{self.parent_pk} "
            f"WHERE c.{self.fk_column} IS NOT NULL "
            f"  AND p.{self.parent_pk} IS NULL "
            f"LIMIT {self.sample_limit}"
        )
        rows = list(conn.execute(sql))
        if not rows:
            return []
        sample = tuple(str(r["rid"]) for r in rows)
        return [
            Finding(
                rule=self.name,
                severity=Severity.ERROR,
                detail=(
                    f"orphan rows in {self.child_table}.{self.fk_column} "
                    f"-> {self.parent_table}.{self.parent_pk}"
                ),
                table=self.child_table,
                column=self.fk_column,
                row_count=len(rows),
                sample_row_ids=sample,
            )
        ]


@dataclass(slots=True)
class NotNullConstraintValidator:
    """Find rows where a column expected to be NOT NULL is NULL."""

    table: str
    column: str
    primary_key: str = "id"
    sample_limit: int = 10
    name: str = "not_null_violation"

    def check(self, conn: DbConnection) -> list[Finding]:
        sql = (
            f"SELECT {self.primary_key} AS rid "  # noqa: S608
            f"FROM {self.table} "
            f"WHERE {self.column} IS NULL "
            f"LIMIT {self.sample_limit}"
        )
        rows = list(conn.execute(sql))
        if not rows:
            return []
        sample = tuple(str(r["rid"]) for r in rows)
        return [
            Finding(
                rule=self.name,
                severity=Severity.ERROR,
                detail=f"NULL values in {self.table}.{self.column}",
                table=self.table,
                column=self.column,
                row_count=len(rows),
                sample_row_ids=sample,
            )
        ]


@dataclass(slots=True)
class AuditSignatureValidator:
    """Find audit_events rows missing a signature.

    Story 2.4.1 made signing mandatory for new rows; pre-existing rows
    may legitimately have NULL signatures (those are surfaced as a
    ``warning`` so the operator can decide whether to backfill).
    """

    table: str = "audit_events"
    signature_column: str = "signature"
    sample_limit: int = 10
    name: str = "audit_signature_missing"

    def check(self, conn: DbConnection) -> list[Finding]:
        sql = (
            f"SELECT id AS rid FROM {self.table} "  # noqa: S608
            f"WHERE {self.signature_column} IS NULL "
            f"LIMIT {self.sample_limit}"
        )
        rows = list(conn.execute(sql))
        if not rows:
            return []
        sample = tuple(str(r["rid"]) for r in rows)
        return [
            Finding(
                rule=self.name,
                severity=Severity.WARNING,
                detail=(
                    f"{self.table} has rows without an HMAC signature "
                    "(pre-2.4.1 backfill candidates)"
                ),
                table=self.table,
                column=self.signature_column,
                row_count=len(rows),
                sample_row_ids=sample,
            )
        ]


@dataclass(slots=True, frozen=True)
class DbValidationReport:
    """Roll-up of every finding across a validator suite."""

    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(f.severity is Severity.ERROR for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity is Severity.WARNING for f in self.findings)

    def by_severity(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is severity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "findings": [f.to_dict() for f in self.findings],
        }

    def summary_lines(self) -> list[str]:
        if not self.findings:
            return ["DB validation passed: no issues found."]
        out = []
        for f in self.findings:
            target = ".".join(p for p in (f.table, f.column) if p)
            out.append(
                f"[{f.severity.value}] {f.rule}: {target} ({f.row_count} row(s)) — {f.detail}"
            )
        return out


def run_validators(conn: DbConnection, validators: Sequence[Validator]) -> DbValidationReport:
    """Execute every validator and aggregate findings."""
    findings: list[Finding] = []
    for v in validators:
        findings.extend(v.check(conn))
    return DbValidationReport(findings=tuple(findings))


__all__ = [
    "AuditSignatureValidator",
    "DbConnection",
    "DbValidationReport",
    "Finding",
    "ForeignKeyOrphanValidator",
    "NotNullConstraintValidator",
    "Severity",
    "Validator",
    "run_validators",
]
