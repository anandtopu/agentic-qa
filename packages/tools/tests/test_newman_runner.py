"""Unit tests for the Newman runner — Story 1.4.2.

Covers the StubNewmanRunner contract and the report-flattening logic of
SubprocessNewmanRunner (without actually shelling out — we feed a fake
Newman summary into the helper).
"""

from __future__ import annotations

import asyncio
from typing import Any

from aqao_tools.newman import (
    NewmanAssertion,
    NewmanResult,
    StubNewmanRunner,
)
from aqao_tools.newman.runner import _flatten_assertions

_FAKE_EXECUTIONS: list[dict[str, Any]] = [
    {
        "request": {"method": "POST", "url": {"raw": "https://x/charge"}},
        "response": {"code": 200},
        "assertions": [
            {"assertion": "Status code is 200"},
            {
                "assertion": "Body contains id",
                "error": {"message": "AssertionError: id missing"},
            },
        ],
    },
    {
        "request": {"method": "GET", "url": "https://x/health"},
        "response": {"code": 200},
        "assertions": [{"assertion": "Health is 200"}],
    },
]


def test_stub_runner_records_calls_and_returns_default_result() -> None:
    stub = StubNewmanRunner()
    result = asyncio.run(
        stub.run(
            collection={"info": {"name": "Smoke", "schema": "x"}, "item": []},
            environment={"BASE_URL": "https://x"},
        )
    )
    assert isinstance(result, NewmanResult)
    assert result.exit_code == 0
    assert stub.calls[0]["collection_name"] == "Smoke"
    assert stub.calls[0]["environment"] == {"BASE_URL": "https://x"}


def test_stub_runner_returns_scripted_result_when_provided() -> None:
    canned = NewmanResult(
        exit_code=1,
        duration_ms=150,
        total_requests=2,
        failed_assertions=1,
    )
    stub = StubNewmanRunner(result=canned)
    result = asyncio.run(stub.run(collection={"info": {"name": "x"}, "item": []}))
    assert result.exit_code == 1
    assert result.failed_assertions == 1


def test_flatten_assertions_pairs_request_with_each_assertion() -> None:
    flattened = _flatten_assertions(_FAKE_EXECUTIONS)
    assert len(flattened) == 3
    assert flattened[0] == NewmanAssertion(
        name="Status code is 200",
        passed=True,
        request_method="POST",
        request_url="https://x/charge",
        response_status=200,
    )
    failing = flattened[1]
    assert failing.passed is False
    assert "id missing" in (failing.error or "")
    assert flattened[2].request_method == "GET"


def test_succeeded_property() -> None:
    success = NewmanResult(exit_code=0, duration_ms=10, total_requests=1, failed_assertions=0)
    assert success.succeeded
    assert not NewmanResult(
        exit_code=0, duration_ms=10, total_requests=1, failed_assertions=1
    ).succeeded
    assert not NewmanResult(
        exit_code=1, duration_ms=10, total_requests=1, failed_assertions=0
    ).succeeded
