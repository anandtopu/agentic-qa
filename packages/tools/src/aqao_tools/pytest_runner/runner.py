"""pytest+httpx runner for the API Tester's generated suites.

Writes the generated source to a tempfile, invokes ``pytest`` via
``python -m pytest --json-report --json-report-file=...`` under per-run
limits, and parses the structured report. Stdout/stderr are redacted.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from aqao_redaction import Redactor, default_redactor

DEFAULT_TIMEOUT_SECONDS = 600


class TestOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class PytestRunnerError(RuntimeError):
    pass


@dataclass(slots=True)
class TestResult:
    nodeid: str
    outcome: TestOutcome
    duration_ms: int
    longrepr: str | None = None


@dataclass(slots=True)
class PytestResult:
    exit_code: int
    duration_ms: int
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    tests: list[TestResult] = field(default_factory=list)
    stdout_redacted: str = ""
    stderr_redacted: str = ""

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0


class PytestRunner(Protocol):
    async def run(
        self,
        *,
        source_code: str,
        module_name: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PytestResult: ...


@dataclass(slots=True)
class StubPytestRunner:
    result: PytestResult | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        source_code: str,
        module_name: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PytestResult:
        self.calls.append(
            {
                "module_name": module_name,
                "env": dict(env or {}),
                "timeout_seconds": timeout_seconds,
                "source_length": len(source_code),
            }
        )
        if self.result is not None:
            return self.result
        return PytestResult(
            exit_code=0,
            duration_ms=0,
            total=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
        )


@dataclass(slots=True)
class SubprocessPytestRunner:
    python_binary: str = field(default_factory=lambda: sys.executable)
    redactor: Redactor = field(default_factory=default_redactor)

    async def run(
        self,
        *,
        source_code: str,
        module_name: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PytestResult:
        if not shutil.which(self.python_binary):
            raise PytestRunnerError(f"python binary {self.python_binary!r} not found")

        with tempfile.TemporaryDirectory(prefix="aqao-pytest-") as tmp:
            tmp_path = Path(tmp)
            test_path = tmp_path / f"{module_name}.py"
            report_path = tmp_path / "report.json"
            test_path.write_text(source_code, encoding="utf-8")

            args = [
                self.python_binary,
                "-m",
                "pytest",
                str(test_path),
                "--json-report",
                f"--json-report-file={report_path}",
                "-q",
                "--no-header",
            ]
            full_env = {**(env or {})}
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(tmp_path),
                env=full_env or None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            except TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise PytestRunnerError(f"pytest timed out after {timeout_seconds}s") from exc

            stdout_text = self.redactor.redact(stdout.decode("utf-8", "replace"))
            stderr_text = self.redactor.redact(stderr.decode("utf-8", "replace"))

            report: dict[str, Any] = {}
            if report_path.is_file():
                try:
                    report = json.loads(report_path.read_text("utf-8"))
                except json.JSONDecodeError as exc:
                    raise PytestRunnerError(f"pytest report not valid JSON: {exc.msg}") from exc

        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        return PytestResult(
            exit_code=proc.returncode or 0,
            duration_ms=int(report.get("duration", 0) * 1000)
            if isinstance(report.get("duration"), (int, float))
            else 0,
            total=int(summary.get("total", 0)),
            passed=int(summary.get("passed", 0)),
            failed=int(summary.get("failed", 0)),
            errors=int(summary.get("error", 0)),
            skipped=int(summary.get("skipped", 0)),
            tests=_extract_tests(report),
            stdout_redacted=stdout_text,
            stderr_redacted=stderr_text,
        )


def _extract_tests(report: dict[str, Any]) -> list[TestResult]:
    out: list[TestResult] = []
    for entry in report.get("tests", []) or []:
        if not isinstance(entry, dict):
            continue
        outcome_raw = str(entry.get("outcome", "")).lower()
        try:
            outcome = TestOutcome(outcome_raw)
        except ValueError:
            outcome = TestOutcome.ERROR
        duration = entry.get("call", {}).get("duration") or entry.get("duration") or 0
        longrepr_raw = (
            entry.get("call", {}).get("longrepr") if outcome is TestOutcome.FAILED else None
        )
        out.append(
            TestResult(
                nodeid=str(entry.get("nodeid", "")),
                outcome=outcome,
                duration_ms=int(float(duration) * 1000),
                longrepr=str(longrepr_raw) if longrepr_raw else None,
            )
        )
    return out
