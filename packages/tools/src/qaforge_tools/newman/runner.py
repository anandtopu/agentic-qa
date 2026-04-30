"""Newman runner — wraps the Newman CLI as a sandboxed subprocess.

Newman accepts a Postman collection JSON + an environment JSON and emits
JSON-shaped reports via ``--reporters json`` (stdout) or to a file. We
spawn it under per-run resource limits and pipe stdout through the
redactor so secrets never reach logs / evidence.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from qaforge_redaction import Redactor, default_redactor

DEFAULT_BINARY = "newman"
DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes; PRD §14.5 API smoke budget


class NewmanRunnerError(RuntimeError):
    """Newman exited non-zero or its output was unparseable."""


@dataclass(slots=True)
class NewmanAssertion:
    name: str
    passed: bool
    error: str | None = None
    request_method: str | None = None
    request_url: str | None = None
    response_status: int | None = None


@dataclass(slots=True)
class NewmanResult:
    exit_code: int
    duration_ms: int
    total_requests: int
    failed_assertions: int
    assertions: list[NewmanAssertion] = field(default_factory=list)
    raw_summary: dict[str, Any] = field(default_factory=dict)
    stdout_redacted: str = ""
    stderr_redacted: str = ""

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self.failed_assertions == 0


class NewmanRunner(Protocol):
    async def run(
        self,
        *,
        collection: Mapping[str, Any],
        environment: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> NewmanResult: ...


@dataclass(slots=True)
class StubNewmanRunner:
    """Test/dev runner that returns a scripted :class:`NewmanResult`.

    Production callers should pass a :class:`SubprocessNewmanRunner`.
    """

    result: NewmanResult | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        collection: Mapping[str, Any],
        environment: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> NewmanResult:
        self.calls.append(
            {
                "collection_name": collection.get("info", {}).get("name"),
                "environment": dict(environment or {}),
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.result is not None:
            return self.result
        return NewmanResult(
            exit_code=0,
            duration_ms=0,
            total_requests=0,
            failed_assertions=0,
        )


@dataclass(slots=True)
class SubprocessNewmanRunner:
    """Production runner: shells out to the ``newman`` CLI."""

    binary: str = DEFAULT_BINARY
    redactor: Redactor = field(default_factory=default_redactor)

    async def run(
        self,
        *,
        collection: Mapping[str, Any],
        environment: Mapping[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> NewmanResult:
        if shutil.which(self.binary) is None:
            raise NewmanRunnerError(f"newman binary {self.binary!r} not found on PATH")

        with tempfile.TemporaryDirectory(prefix="qaforge-newman-") as tmp:
            tmp_path = Path(tmp)
            collection_path = tmp_path / "collection.json"
            collection_path.write_text(json.dumps(collection), encoding="utf-8")

            env_path: Path | None = None
            if environment:
                env_path = tmp_path / "environment.json"
                env_path.write_text(
                    json.dumps(
                        {
                            "name": "qaforge-run",
                            "values": [
                                {"key": k, "value": v, "enabled": True}
                                for k, v in environment.items()
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

            report_path = tmp_path / "report.json"
            args = [
                self.binary,
                "run",
                str(collection_path),
                "--reporters",
                "json",
                "--reporter-json-export",
                str(report_path),
            ]
            if env_path is not None:
                args.extend(["--environment", str(env_path)])

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            except TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise NewmanRunnerError(f"newman timed out after {timeout_seconds}s") from exc

            stdout_text = self.redactor.redact(stdout.decode("utf-8", "replace"))
            stderr_text = self.redactor.redact(stderr.decode("utf-8", "replace"))

            summary: dict[str, Any] = {}
            if report_path.is_file():
                try:
                    summary = json.loads(report_path.read_text("utf-8"))
                except json.JSONDecodeError as exc:
                    raise NewmanRunnerError(f"newman report was not valid JSON: {exc.msg}") from exc

        run = summary.get("run") if isinstance(summary, dict) else {}
        stats = run.get("stats", {}) if isinstance(run, dict) else {}
        executions = run.get("executions", []) if isinstance(run, dict) else []
        timings = run.get("timings", {}) if isinstance(run, dict) else {}
        duration_ms = int(timings.get("completed", 0) - timings.get("started", 0))

        assertions = _flatten_assertions(executions)

        return NewmanResult(
            exit_code=proc.returncode or 0,
            duration_ms=max(0, duration_ms),
            total_requests=int(stats.get("requests", {}).get("total", 0))
            if isinstance(stats.get("requests"), dict)
            else 0,
            failed_assertions=sum(1 for a in assertions if not a.passed),
            assertions=assertions,
            raw_summary=summary,
            stdout_redacted=stdout_text,
            stderr_redacted=stderr_text,
        )


def _flatten_assertions(executions: list[Any]) -> list[NewmanAssertion]:
    out: list[NewmanAssertion] = []
    for execution in executions or []:
        if not isinstance(execution, dict):
            continue
        request = execution.get("request") or {}
        url = request.get("url")
        url_str = url.get("raw") or "" if isinstance(url, dict) else str(url or "")
        method = str(request.get("method") or "GET")
        response = execution.get("response") or {}
        status = response.get("code") if isinstance(response, dict) else None

        for assertion in execution.get("assertions") or []:
            if not isinstance(assertion, dict):
                continue
            error = assertion.get("error") or {}
            error_msg = str(error.get("message")) if isinstance(error, dict) and error else None
            out.append(
                NewmanAssertion(
                    name=str(assertion.get("assertion") or ""),
                    passed=error_msg is None,
                    error=error_msg,
                    request_method=method,
                    request_url=url_str,
                    response_status=int(status) if isinstance(status, int) else None,
                )
            )
    return out
