"""DestructiveSqlGuard — Story 2.2.3.

Glues the SQL classifier to the approval gate. Given a SQL script
about to be executed by the DB tool, the guard either:

* returns ``None`` if every statement is read-only — caller proceeds
  with execution; or
* returns an :class:`ApprovalGateStep` configured for the
  ``destructive_sql`` event so the workflow runner pauses for human
  sign-off before the tool runs.

A second helper, :func:`assert_read_only`, raises
:class:`DestructiveSqlBlocked` synchronously when a workflow author
wants to fail loud rather than route through approval (e.g. inside a
read-only validator).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qaforge_agents.db_validator.parser import (
    SqlStatement,
    SqlStatementClassifier,
    SqlStatementKind,
)
from qaforge_agents.runtime.approval import ApprovalGate, ApprovalGateStep


class DestructiveSqlBlocked(RuntimeError):  # noqa: N818 - public name predates rule
    """A destructive statement reached a read-only execution path."""

    def __init__(self, statements: tuple[SqlStatement, ...]) -> None:
        leading = ", ".join(s.leading_verb for s in statements)
        super().__init__(f"destructive SQL blocked: {len(statements)} statement(s) [{leading}]")
        self.statements = statements


@dataclass(slots=True)
class DestructiveSqlGuard:
    """Orchestrates the policy ``destructive SQL -> approval gate``."""

    gate: ApprovalGate
    classifier: SqlStatementClassifier = field(default_factory=SqlStatementClassifier)
    event_type: str = "destructive_sql"
    step_name: str = "destructive_sql_approval"

    def maybe_build_step(
        self, *, sql: str, subject: str, reason: str | None = None
    ) -> ApprovalGateStep | None:
        """Return an :class:`ApprovalGateStep` if the SQL needs review,
        else ``None``.

        The step's ``extra_context`` carries the destructive verbs we
        spotted so the reviewer's UI can show them at a glance.
        """
        destructive = self._destructive_statements(sql)
        if not destructive:
            return None
        return ApprovalGateStep(
            name=self.step_name,
            event_type=self.event_type,
            subject=subject,
            gate=self.gate,
            reason=reason,
            extra_context={
                "destructive_verbs": [s.leading_verb for s in destructive],
                "statement_count": len(destructive),
            },
        )

    def assert_read_only(self, sql: str) -> None:
        """Raise :class:`DestructiveSqlBlocked` if the SQL is not
        read-only. Used by validator code paths that must never write."""
        destructive = self._destructive_statements(sql)
        if destructive:
            raise DestructiveSqlBlocked(destructive)

    def _destructive_statements(self, sql: str) -> tuple[SqlStatement, ...]:
        statements = self.classifier.classify(sql)
        return tuple(s for s in statements if s.kind is not SqlStatementKind.READ_ONLY)


__all__ = [
    "DestructiveSqlBlocked",
    "DestructiveSqlGuard",
]
