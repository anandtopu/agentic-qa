"""JSONL dataset loader.

Layout:

* ``packages/eval/datasets/<agent>/<vN>.jsonl`` — one row per case.

Each row is :class:`EvalCase` JSON. Versioned files allow pinning a
scorecard to a specific dataset revision.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from qaforge_eval.types import EvalCase


@dataclass(slots=True)
class EvalDataset:
    name: str
    version: str
    cases: list[EvalCase]
    source_path: Path | None = None

    def __iter__(self) -> Iterator[EvalCase]:
        return iter(self.cases)

    def __len__(self) -> int:
        return len(self.cases)


def load_jsonl(path: Path) -> list[EvalCase]:
    """Load a JSONL file into :class:`EvalCase` rows.

    Empty / blank lines are skipped. Comment lines starting with ``#``
    in the first column are ignored to keep dataset files diff-friendly.
    """
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            cases.append(EvalCase.model_validate(json.loads(line)))
    return cases


def load_dataset(
    *,
    base_dir: Path,
    agent: str,
    version: str,
) -> EvalDataset:
    """Load ``<base_dir>/<agent>/<version>.jsonl`` into an :class:`EvalDataset`."""
    path = base_dir / agent / f"{version}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"dataset not found: {path}")
    cases = load_jsonl(path)
    return EvalDataset(
        name=agent,
        version=version,
        cases=cases,
        source_path=path,
    )
