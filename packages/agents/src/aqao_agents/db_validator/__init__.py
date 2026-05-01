"""DB Validation Agent — Epic 2.2.

Read-only validators that check a tenant's tested database for
integrity issues (orphans, missing FKs, NULLs in NOT-NULL columns,
audit-signature gaps). The agent's destructive-SQL pathway routes
``DELETE/UPDATE/DROP/TRUNCATE/ALTER`` statements through the human
approval gate before they ever reach the runner.

Public surface:

* :class:`Validator` Protocol + bundled implementations.
* :class:`DbValidationReport` aggregating findings across validators.
* :class:`SqlStatementClassifier` for tagging SQL strings as read-only
  vs destructive.
* :class:`SnapshotDiffer` for pre/post row-hash diffs (Story 2.2.2).
"""

from aqao_agents.db_validator.guard import (
    DestructiveSqlBlocked,
    DestructiveSqlGuard,
)
from aqao_agents.db_validator.parser import (
    DESTRUCTIVE_VERBS,
    READ_ONLY_VERBS,
    SqlStatement,
    SqlStatementClassifier,
    SqlStatementKind,
    classify_sql,
)
from aqao_agents.db_validator.snapshot import (
    SnapshotBudgetExceeded,
    SnapshotDiff,
    SnapshotDiffer,
    SnapshotRow,
    TableSnapshot,
)
from aqao_agents.db_validator.validators import (
    AuditSignatureValidator,
    DbConnection,
    DbValidationReport,
    Finding,
    ForeignKeyOrphanValidator,
    NotNullConstraintValidator,
    Severity,
    Validator,
    run_validators,
)

__all__ = [
    "DESTRUCTIVE_VERBS",
    "READ_ONLY_VERBS",
    "AuditSignatureValidator",
    "DbConnection",
    "DbValidationReport",
    "DestructiveSqlBlocked",
    "DestructiveSqlGuard",
    "Finding",
    "ForeignKeyOrphanValidator",
    "NotNullConstraintValidator",
    "Severity",
    "SnapshotBudgetExceeded",
    "SnapshotDiff",
    "SnapshotDiffer",
    "SnapshotRow",
    "SqlStatement",
    "SqlStatementClassifier",
    "SqlStatementKind",
    "TableSnapshot",
    "Validator",
    "classify_sql",
    "run_validators",
]
