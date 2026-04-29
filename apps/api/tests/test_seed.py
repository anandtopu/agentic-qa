"""Unit-level tests for scripts/seed.py.

The full DB round-trip is exercised by an integration run in CI when
docker-compose is up. Here we just confirm the orchestration: the main
pipeline runs each step in order, returns 0, and surfaces step failures
as a non-zero exit code.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = REPO_ROOT / "scripts" / "seed.py"


def _load_seed_module() -> Any:
    spec = importlib.util.spec_from_file_location("qaforge_seed_under_test", SEED_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["qaforge_seed_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_main_runs_each_step_in_order() -> None:
    seed = _load_seed_module()
    calls: list[str] = []

    def step_a(_: object) -> None:
        calls.append("a")

    def step_b(_: object) -> None:
        calls.append("b")

    assert seed.main(steps=[step_a, step_b]) == 0
    assert calls == ["a", "b"]


def test_main_propagates_step_exit_code() -> None:
    seed = _load_seed_module()

    def boom(_: object) -> None:
        raise SystemExit(7)

    with pytest.raises(SystemExit) as exc_info:
        seed.main(steps=[boom])
    assert exc_info.value.code == 7
