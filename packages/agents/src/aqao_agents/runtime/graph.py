"""WorkflowGraph — declarative ordered list of :class:`Step` objects.

Phase 1 keeps the graph linear (no branching) — the runtime walks the
list in order. The Step API is shaped to support DAG-style branching
(``next_state``, ``pause``) so a Phase-2 LangGraph swap-in does not
need a graph-shape migration.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from aqao_agents.runtime.step import Step


@dataclass(slots=True)
class WorkflowGraph:
    name: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        names = [s.name for s in self.steps]
        if len(set(names)) != len(names):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"WorkflowGraph step names must be unique; duplicates: {duplicates}")

    @classmethod
    def of(cls, name: str, steps: Sequence[Step]) -> WorkflowGraph:
        return cls(name=name, steps=tuple(steps))

    def __iter__(self) -> Iterator[Step]:
        return iter(self.steps)

    def __len__(self) -> int:
        return len(self.steps)
