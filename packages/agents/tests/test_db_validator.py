"""Unit tests for the DB Validation agent — Epic 2.2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from aqao_agents.db_validator import (
    DESTRUCTIVE_VERBS,
    AuditSignatureValidator,
    Finding,
    ForeignKeyOrphanValidator,
    NotNullConstraintValidator,
    Severity,
    SnapshotBudgetExceeded,
    SnapshotDiffer,
    SqlStatementClassifier,
    SqlStatementKind,
    classify_sql,
    run_validators,
)


class _StubConnection:
    """Records every SQL string and returns canned rows per query."""

    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        self.calls.append(sql)
        # Cheap key match — tests pass the leading verb-clause.
        for fragment, rows in self._responses.items():
            if fragment in sql:
                return iter(rows)
        return iter([])


# ---------------------------------------------------------------- validators


def test_orphan_validator_emits_error_finding_when_orphans_exist() -> None:
    conn = _StubConnection(
        {
            "FROM child_table c": [{"rid": "row-1"}, {"rid": "row-2"}],
        }
    )
    validator = ForeignKeyOrphanValidator(
        child_table="child_table",
        fk_column="parent_id",
        parent_table="parent_table",
    )
    findings = validator.check(conn)
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].row_count == 2
    assert findings[0].sample_row_ids == ("row-1", "row-2")


def test_orphan_validator_returns_empty_when_clean() -> None:
    conn = _StubConnection({})  # no rows for any query
    validator = ForeignKeyOrphanValidator(
        child_table="child_table",
        fk_column="parent_id",
        parent_table="parent_table",
    )
    assert validator.check(conn) == []


def test_orphan_validator_query_is_select_only() -> None:
    """AC: 'no write side effects'. Smoke-check the SQL we emit."""
    conn = _StubConnection({})
    ForeignKeyOrphanValidator(
        child_table="child_table",
        fk_column="parent_id",
        parent_table="parent_table",
    ).check(conn)
    assert any(c.upper().startswith("SELECT") for c in conn.calls)
    for c in conn.calls:
        for verb in DESTRUCTIVE_VERBS:
            assert f" {verb} " not in f" {c.upper()} "


def test_not_null_validator_emits_error_finding() -> None:
    conn = _StubConnection({"FROM users": [{"rid": "u-1"}]})
    findings = NotNullConstraintValidator(table="users", column="email").check(conn)
    assert findings[0].severity is Severity.ERROR
    assert findings[0].column == "email"


def test_audit_signature_validator_emits_warning_only() -> None:
    conn = _StubConnection({"FROM audit_events": [{"rid": "a-1"}]})
    findings = AuditSignatureValidator().check(conn)
    assert findings[0].severity is Severity.WARNING


def test_run_validators_aggregates_into_report() -> None:
    conn = _StubConnection(
        {
            "FROM child_table c": [{"rid": "row-1"}],
            "FROM users": [{"rid": "u-1"}],
        }
    )
    report = run_validators(
        conn,
        [
            ForeignKeyOrphanValidator(
                child_table="child_table",
                fk_column="parent_id",
                parent_table="parent_table",
            ),
            NotNullConstraintValidator(table="users", column="email"),
            AuditSignatureValidator(),
        ],
    )
    assert report.has_errors
    assert len(report.findings) == 2  # audit signature query returns nothing


def test_report_summary_lines_describe_findings() -> None:
    findings = (
        Finding(
            rule="foreign_key_orphan",
            severity=Severity.ERROR,
            detail="orphans",
            table="orders",
            column="user_id",
            row_count=3,
        ),
    )
    from aqao_agents.db_validator import DbValidationReport

    text = "\n".join(DbValidationReport(findings=findings).summary_lines())
    assert "[error]" in text
    assert "orders.user_id" in text


# ---------------------------------------------------------------- SQL parser


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users",
        "SELECT id FROM users WHERE deleted_at IS NULL",
        "EXPLAIN SELECT * FROM orders",
        "  SHOW TABLES  ",
        "WITH active AS (SELECT id FROM users WHERE active) SELECT * FROM active",
    ],
)
def test_classifier_marks_read_only_statements(sql: str) -> None:
    statements = classify_sql(sql)
    assert all(s.kind is SqlStatementKind.READ_ONLY for s in statements)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM users WHERE id = 1",
        "UPDATE users SET name = 'x'",
        "DROP TABLE legacy",
        "TRUNCATE TABLE evidence",
        "ALTER TABLE users ADD COLUMN new_col text",
        "INSERT INTO users (id) VALUES (1)",
        "GRANT ALL ON users TO bob",
        "VACUUM ANALYZE users",
    ],
)
def test_classifier_marks_destructive_statements(sql: str) -> None:
    statements = classify_sql(sql)
    assert any(s.is_destructive for s in statements)


def test_classifier_handles_with_destructive_inner_verb() -> None:
    sql = (
        "WITH soft AS (SELECT id FROM users WHERE inactive) "
        "DELETE FROM users WHERE id IN (SELECT id FROM soft)"
    )
    statements = classify_sql(sql)
    assert statements[0].kind is SqlStatementKind.DESTRUCTIVE


def test_classifier_splits_multi_statement_scripts() -> None:
    sql = "SELECT 1; DELETE FROM users WHERE id = 1; SELECT 2"
    statements = classify_sql(sql)
    assert [s.kind for s in statements] == [
        SqlStatementKind.READ_ONLY,
        SqlStatementKind.DESTRUCTIVE,
        SqlStatementKind.READ_ONLY,
    ]


def test_classifier_ignores_destructive_verbs_in_strings_and_comments() -> None:
    sql = """
    -- DROP TABLE legacy
    SELECT 'DELETE FROM users' AS demo
    /* TRUNCATE TABLE evidence */
    """
    statements = classify_sql(sql)
    assert len(statements) == 1
    assert statements[0].kind is SqlStatementKind.READ_ONLY


def test_classifier_unknown_verb_treated_as_destructive() -> None:
    statements = classify_sql("LOCK TABLE users IN ACCESS EXCLUSIVE MODE")
    assert statements[0].kind is SqlStatementKind.UNKNOWN
    assert statements[0].is_destructive  # safer default


def test_is_script_destructive_short_circuits_on_first_destructive() -> None:
    classifier = SqlStatementClassifier()
    assert classifier.is_script_destructive("SELECT 1; DROP TABLE x")
    assert not classifier.is_script_destructive("SELECT 1; SELECT 2")


def test_classifier_extra_destructive_verbs_are_honoured() -> None:
    classifier = SqlStatementClassifier(extra_destructive_verbs=("LOCK",))
    statements = classifier.classify("LOCK TABLE users")
    assert statements[0].kind is SqlStatementKind.DESTRUCTIVE


# ---------------------------------------------------------------- snapshots


def test_snapshot_capture_and_clean_diff() -> None:
    differ = SnapshotDiffer()
    rows = [
        {"id": 1, "name": "alice", "age": 30},
        {"id": 2, "name": "bob", "age": 28},
    ]
    before = differ.capture(table="users", rows=rows)
    after = differ.capture(table="users", rows=rows)
    diff = differ.diff(before=before, after=after)
    assert diff.is_clean


def test_snapshot_diff_detects_added_removed_changed() -> None:
    differ = SnapshotDiffer()
    before_rows = [
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
        {"id": 3, "name": "carol"},
    ]
    after_rows = [
        {"id": 1, "name": "alice"},  # unchanged
        {"id": 2, "name": "BOB"},  # changed
        {"id": 4, "name": "dave"},  # added (3 removed)
    ]
    before = differ.capture(table="users", rows=before_rows)
    after = differ.capture(table="users", rows=after_rows)
    diff = differ.diff(before=before, after=after)
    assert diff.added == ("4",)
    assert diff.removed == ("3",)
    assert diff.changed == ("2",)
    assert not diff.is_clean


def test_snapshot_capture_aborts_when_budget_exceeded() -> None:
    differ = SnapshotDiffer(row_budget=2)
    rows = [{"id": i} for i in range(5)]
    with pytest.raises(SnapshotBudgetExceeded) as exc:
        differ.capture(table="big_table", rows=rows)
    assert exc.value.table == "big_table"
    assert exc.value.budget == 2


def test_snapshot_capture_rejects_missing_primary_key() -> None:
    differ = SnapshotDiffer()
    with pytest.raises(ValueError, match="primary key"):
        differ.capture(table="t", rows=[{"name": "a"}])


def test_snapshot_diff_rejects_mismatched_tables() -> None:
    differ = SnapshotDiffer()
    a = differ.capture(table="t1", rows=[{"id": 1}])
    b = differ.capture(table="t2", rows=[{"id": 1}])
    with pytest.raises(ValueError, match="different tables"):
        differ.diff(before=a, after=b)


def test_snapshot_digest_is_order_independent() -> None:
    differ = SnapshotDiffer()
    a = differ.capture(table="t", rows=[{"id": 1, "a": 1, "b": 2}])
    b = differ.capture(table="t", rows=[{"b": 2, "a": 1, "id": 1}])
    assert differ.diff(before=a, after=b).is_clean
