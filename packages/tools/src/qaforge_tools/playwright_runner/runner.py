"""Playwright runner implementations."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from qaforge_redaction import Redactor, default_redactor

DEFAULT_BINARY = "npx"
DEFAULT_TIMEOUT_SECONDS = 900  # PRD §14.5 UI smoke budget = 10 min; pad for trace upload


class PlaywrightTestOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
    INTERRUPTED = "interrupted"


class PlaywrightRunnerError(RuntimeError):
    pass


@dataclass(slots=True)
class PlaywrightArtifact:
    kind: str  # "trace" | "video" | "screenshot"
    path: str
    test_id: str | None = None


@dataclass(slots=True)
class PlaywrightTestResult:
    test_id: str
    title: str
    outcome: PlaywrightTestOutcome
    duration_ms: int
    error_message: str | None = None
    artifacts: list[PlaywrightArtifact] = field(default_factory=list)


@dataclass(slots=True)
class PlaywrightResult:
    exit_code: int
    duration_ms: int
    total: int
    passed: int
    failed: int
    skipped: int
    tests: list[PlaywrightTestResult] = field(default_factory=list)
    stdout_redacted: str = ""
    stderr_redacted: str = ""
    raw_report: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self.failed == 0


class PlaywrightRunner(Protocol):
    async def run(
        self,
        *,
        spec_filename: str,
        source_code: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PlaywrightResult: ...


@dataclass(slots=True)
class StubPlaywrightRunner:
    result: PlaywrightResult | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        spec_filename: str,
        source_code: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PlaywrightResult:
        self.calls.append(
            {
                "spec_filename": spec_filename,
                "source_length": len(source_code),
                "env": dict(env or {}),
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.result is not None:
            return self.result
        return PlaywrightResult(
            exit_code=0,
            duration_ms=0,
            total=0,
            passed=0,
            failed=0,
            skipped=0,
        )


_PW_CONFIG = """\
import {{ defineConfig }} from '@playwright/test';

export default defineConfig({{
  testDir: '.',
  timeout: 60_000,
  retries: 0,
  reporter: [['json', {{ outputFile: '{report_path}' }}]],
  use: {{
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  }},
}});
"""


@dataclass(slots=True)
class SubprocessPlaywrightRunner:
    """Production runner — shells out to ``npx playwright test``."""

    npx_binary: str = DEFAULT_BINARY
    redactor: Redactor = field(default_factory=default_redactor)

    async def run(
        self,
        *,
        spec_filename: str,
        source_code: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> PlaywrightResult:
        if shutil.which(self.npx_binary) is None:
            raise PlaywrightRunnerError(f"npx binary {self.npx_binary!r} not found on PATH")

        with tempfile.TemporaryDirectory(prefix="qaforge-playwright-") as tmp:
            tmp_path = Path(tmp)
            spec_path = tmp_path / spec_filename
            spec_path.write_text(source_code, encoding="utf-8")
            report_path = tmp_path / "report.json"
            config_path = tmp_path / "playwright.config.ts"
            config_path.write_text(
                _PW_CONFIG.format(report_path=report_path.as_posix()),
                encoding="utf-8",
            )

            args = [
                self.npx_binary,
                "playwright",
                "test",
                str(spec_path),
                "--config",
                str(config_path),
                "--reporter=json",
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
                raise PlaywrightRunnerError(
                    f"playwright timed out after {timeout_seconds}s"
                ) from exc

            stdout_text = self.redactor.redact(stdout.decode("utf-8", "replace"))
            stderr_text = self.redactor.redact(stderr.decode("utf-8", "replace"))

            report: dict[str, Any] = {}
            if report_path.is_file():
                try:
                    report = json.loads(report_path.read_text("utf-8"))
                except json.JSONDecodeError as exc:
                    raise PlaywrightRunnerError(
                        f"playwright report not valid JSON: {exc.msg}"
                    ) from exc

        tests = _flatten_tests(report)
        passed = sum(1 for t in tests if t.outcome is PlaywrightTestOutcome.PASSED)
        failed = sum(1 for t in tests if t.outcome is PlaywrightTestOutcome.FAILED)
        skipped = sum(1 for t in tests if t.outcome is PlaywrightTestOutcome.SKIPPED)

        return PlaywrightResult(
            exit_code=proc.returncode or 0,
            duration_ms=int(report.get("duration", 0))
            if isinstance(report.get("duration"), (int, float))
            else 0,
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
            stdout_redacted=stdout_text,
            stderr_redacted=stderr_text,
            raw_report=report,
        )


def _flatten_tests(report: dict[str, Any]) -> list[PlaywrightTestResult]:
    out: list[PlaywrightTestResult] = []
    suites = report.get("suites", []) if isinstance(report, dict) else []
    for suite in suites or []:
        if not isinstance(suite, dict):
            continue
        for spec in suite.get("specs", []) or []:
            if not isinstance(spec, dict):
                continue
            tests = spec.get("tests", []) or []
            for test in tests:
                if not isinstance(test, dict):
                    continue
                results = test.get("results", []) or []
                last = results[-1] if results else {}
                outcome_raw = (
                    str(last.get("status", "")).lower() or str(test.get("status", "")).lower()
                )
                try:
                    outcome = PlaywrightTestOutcome(outcome_raw)
                except ValueError:
                    outcome = PlaywrightTestOutcome.INTERRUPTED
                duration = last.get("duration", 0) if isinstance(last, dict) else 0
                error_msg = None
                if isinstance(last, dict):
                    err = last.get("error") or {}
                    if isinstance(err, dict):
                        error_msg = err.get("message")

                artifacts: list[PlaywrightArtifact] = []
                attachments = last.get("attachments", []) if isinstance(last, dict) else []
                for att in attachments or []:
                    if not isinstance(att, dict):
                        continue
                    name = str(att.get("name") or "")
                    path = str(att.get("path") or "")
                    if not path:
                        continue
                    kind = (
                        "trace" if "trace" in name else "video" if "video" in name else "screenshot"
                    )
                    artifacts.append(
                        PlaywrightArtifact(
                            kind=kind, path=path, test_id=str(test.get("testId") or "")
                        )
                    )

                out.append(
                    PlaywrightTestResult(
                        test_id=str(test.get("testId") or ""),
                        title=str(spec.get("title") or ""),
                        outcome=outcome,
                        duration_ms=int(duration),
                        error_message=str(error_msg) if error_msg else None,
                        artifacts=artifacts,
                    )
                )
    return out
