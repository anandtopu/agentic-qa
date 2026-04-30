"""Unit tests for the Playwright runner — Story 1.5.2.

The Stub is what every higher-level test composes against. We also feed
fake JSON-reporter shapes into the helper to verify the flattening logic
that the Subprocess runner relies on.
"""

from __future__ import annotations

import asyncio
from typing import Any

from qaforge_tools.playwright_runner import (
    PlaywrightArtifact,
    PlaywrightResult,
    PlaywrightTestOutcome,
    StubPlaywrightRunner,
)
from qaforge_tools.playwright_runner.runner import _flatten_tests

_FAKE_REPORT: dict[str, Any] = {
    "duration": 1234,
    "suites": [
        {
            "specs": [
                {
                    "title": "login",
                    "tests": [
                        {
                            "testId": "t1",
                            "results": [
                                {
                                    "status": "passed",
                                    "duration": 1100,
                                    "attachments": [
                                        {"name": "trace.zip", "path": "/tmp/trace.zip"}
                                    ],
                                }
                            ],
                        },
                    ],
                },
                {
                    "title": "checkout",
                    "tests": [
                        {
                            "testId": "t2",
                            "results": [
                                {
                                    "status": "failed",
                                    "duration": 800,
                                    "error": {"message": "expected click visible"},
                                    "attachments": [
                                        {"name": "video.webm", "path": "/tmp/video.webm"},
                                        {
                                            "name": "screenshot.png",
                                            "path": "/tmp/shot.png",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ]
        }
    ],
}


def test_stub_default_returns_passing_result() -> None:
    stub = StubPlaywrightRunner()
    result = asyncio.run(stub.run(spec_filename="x.spec.ts", source_code="// hi"))
    assert isinstance(result, PlaywrightResult)
    assert result.exit_code == 0
    assert stub.calls[0]["spec_filename"] == "x.spec.ts"


def test_stub_returns_scripted_result() -> None:
    canned = PlaywrightResult(
        exit_code=1,
        duration_ms=500,
        total=1,
        passed=0,
        failed=1,
        skipped=0,
    )
    stub = StubPlaywrightRunner(result=canned)
    result = asyncio.run(stub.run(spec_filename="x.spec.ts", source_code="// hi"))
    assert result.failed == 1


def test_flatten_tests_handles_attachments_and_outcomes() -> None:
    tests = _flatten_tests(_FAKE_REPORT)
    by_id = {t.test_id: t for t in tests}
    assert by_id["t1"].outcome is PlaywrightTestOutcome.PASSED
    assert by_id["t1"].duration_ms == 1100
    assert any(a.kind == "trace" and a.path == "/tmp/trace.zip" for a in by_id["t1"].artifacts)
    failed = by_id["t2"]
    assert failed.outcome is PlaywrightTestOutcome.FAILED
    assert failed.error_message == "expected click visible"
    kinds = {a.kind for a in failed.artifacts}
    assert kinds == {"video", "screenshot"}


def test_succeeded_property() -> None:
    ok = PlaywrightResult(exit_code=0, duration_ms=10, total=1, passed=1, failed=0, skipped=0)
    assert ok.succeeded
    failing = PlaywrightResult(exit_code=1, duration_ms=10, total=1, passed=0, failed=1, skipped=0)
    assert not failing.succeeded


def test_artifact_dataclass_round_trip() -> None:
    art = PlaywrightArtifact(kind="trace", path="/x", test_id="t1")
    assert art.kind == "trace"
    assert art.test_id == "t1"
