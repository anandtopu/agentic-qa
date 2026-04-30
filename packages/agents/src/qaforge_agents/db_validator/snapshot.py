"""Pre/post snapshot diffing — Story 2.2.2.

Captures a row-hash snapshot of a target table before a test run and
diffs it against a post-run snapshot, surfacing rows added, removed,
or whose payload changed. The diff is bounded by ``row_budget`` so a
runaway snapshot can't OOM the agent.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


class SnapshotBudgetExceeded(RuntimeError):  # noqa: N818 - public name predates rule
    """Snapshot would exceed the configured row budget. Story 2.2.2 AC
    requires this to abort with a clear error rather than silently
    truncating."""

    def __init__(self, table: str, budget: int) -> None:
        super().__init__(f"snapshot for {table!r} exceeded row budget {budget}")
        self.table = table
        self.budget = budget


@dataclass(slots=True, frozen=True)
class SnapshotRow:
    row_id: str
    digest: str

    @classmethod
    def from_mapping(cls, *, row_id: str, payload: Mapping[str, Any]) -> SnapshotRow:
        return cls(row_id=row_id, digest=_digest(payload))


@dataclass(slots=True, frozen=True)
class TableSnapshot:
    table: str
    rows: tuple[SnapshotRow, ...]

    @property
    def row_index(self) -> dict[str, str]:
        return {r.row_id: r.digest for r in self.rows}


@dataclass(slots=True, frozen=True)
class SnapshotDiff:
    table: str
    added: tuple[str, ...] = field(default_factory=tuple)
    removed: tuple[str, ...] = field(default_factory=tuple)
    changed: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
        }


@dataclass(slots=True)
class SnapshotDiffer:
    """Build :class:`TableSnapshot`\\ s and diff them.

    ``row_budget`` is the per-table cap; once exceeded the snapshot is
    aborted with :class:`SnapshotBudgetExceeded` rather than truncating.
    Capture is implemented over an iterable of mappings so callers can
    stream rows from a SQLAlchemy ``Connection.execution_options(
    yield_per=...)`` cursor without materialising everything in memory.
    """

    row_budget: int = 100_000

    def capture(
        self,
        *,
        table: str,
        rows: Iterable[Mapping[str, Any]],
        primary_key: str = "id",
    ) -> TableSnapshot:
        captured: list[SnapshotRow] = []
        for row in rows:
            if len(captured) >= self.row_budget:
                raise SnapshotBudgetExceeded(table, self.row_budget)
            row_id = row.get(primary_key)
            if row_id is None:
                raise ValueError(f"row in {table!r} is missing primary key {primary_key!r}")
            captured.append(SnapshotRow.from_mapping(row_id=str(row_id), payload=row))
        return TableSnapshot(table=table, rows=tuple(captured))

    def diff(self, *, before: TableSnapshot, after: TableSnapshot) -> SnapshotDiff:
        if before.table != after.table:
            raise ValueError(
                f"cannot diff snapshots of different tables: {before.table!r} vs {after.table!r}"
            )
        before_idx = before.row_index
        after_idx = after.row_index

        added = tuple(sorted(set(after_idx) - set(before_idx)))
        removed = tuple(sorted(set(before_idx) - set(after_idx)))
        changed = tuple(
            sorted(
                rid for rid in set(before_idx) & set(after_idx) if before_idx[rid] != after_idx[rid]
            )
        )
        return SnapshotDiff(table=before.table, added=added, removed=removed, changed=changed)


def _digest(payload: Mapping[str, Any]) -> str:
    """Stable hex digest of a row payload — order-independent so two
    cursor runs with different column orders still produce the same
    hash for an unchanged row."""
    parts = [f"{k}={payload[k]!r}" for k in sorted(payload)]
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


__all__ = [
    "SnapshotBudgetExceeded",
    "SnapshotDiff",
    "SnapshotDiffer",
    "SnapshotRow",
    "TableSnapshot",
]
