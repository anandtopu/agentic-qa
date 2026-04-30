"""Unit tests for the pytest runner — Story 1.4.2."""

from __future__ import annotations

import asyncio
from typing import Any

from qaforge_tools.pytest_runner import (
    PytestResult,
    StubPytestRunner,
    TestOutcome,
)
from qaforge_tools.pytest_runner.runner import _extract_tests

_FAKE_REPORT: dict[str, Any] = {
    "summary": {"total": 3, "passed": 2, "failed": 1, "error": 0, "skipped": 0},
    "duration": 0.42,
    "tests": [
        {"nodeid": "test_x.py::test_a", "outcome": "passed", "call": {"duration": 0.01}},
        {"nodeid": "test_x.py::test_b", "outcome": "passed", "call": {"duration": 0.02}},
        {
            "nodeid": "test_x.py::test_c",
            "outcome": "failed",
            "call": {"duration": 0.05, "longrepr": "AssertionError: 200 != 201"},
        },
    ],
}


def test_stub_runner_default_returns_empty_passing_result() -> None:
    stub = StubPytestRunner()
    result = asyncio.run(stub.run(source_code="def test_x(): assert True", module_name="test_x"))
    assert isinstance(result, PytestResult)
    assert result.exit_code == 0
    assert stub.calls[0]["module_name"] == "test_x"


def test_stub_runner_returns_scripted_result() -> None:
    canned = PytestResult(
        exit_code=1, duration_ms=100, total=2, passed=1, failed=1, errors=0, skipped=0
    )
    stub = StubPytestRunner(result=canned)
    result = asyncio.run(stub.run(source_code="x", module_name="t"))
    assert result.failed == 1


def test_extract_tests_maps_outcomes_and_durations() -> None:
    tests = _extract_tests(_FAKE_REPORT)
    by_node = {t.nodeid: t for t in tests}
    assert by_node["test_x.py::test_a"].outcome is TestOutcome.PASSED
    assert by_node["test_x.py::test_a"].duration_ms == 10
    failed = by_node["test_x.py::test_c"]
    assert failed.outcome is TestOutcome.FAILED
    assert failed.longrepr is not None and "200 != 201" in failed.longrepr


def test_succeeded_property() -> None:
    ok = PytestResult(exit_code=0, duration_ms=10, total=1, passed=1, failed=0, errors=0, skipped=0)
    assert ok.succeeded
    failing = PytestResult(
        exit_code=1, duration_ms=10, total=1, passed=0, failed=1, errors=0, skipped=0
    )
    assert not failing.succeeded
