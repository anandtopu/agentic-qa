"""AQAOClient + AsyncAQAOClient — Story 5.3.

The clients are intentionally **transport-thin** — they manage auth
headers, idempotency keys, and the retry policy, but they don't
re-type every endpoint. Resource-specific helpers (`workspaces.create`,
`testRuns.failures`, etc.) wrap the bare REST calls in a way that's
discoverable from an IDE; callers who want full typing run the
OpenAPI codegen variant (deferred).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class _Transport:
    """Minimal transport surface the resource helpers consume.

    Production deployments wrap ``httpx`` via :class:`HttpxTransport`;
    tests inject a stub that records the calls.
    """

    base_url: str
    token: str
    tenant_id: str
    role: str | None = None
    timeout_seconds: float = 30.0
    sender: Callable[..., dict[str, Any]] | None = None

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-AQAO-Tenant-Id": self.tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.role is not None:
            headers["X-AQAO-Role"] = self.role
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if self.sender is None:
            raise RuntimeError(
                "Transport.sender is unset — wire either HttpxTransport "
                "or a test stub before issuing requests"
            )
        extra: dict[str, str] = {}
        if idempotency_key is not None:
            extra["Idempotency-Key"] = idempotency_key
        url = f"{self.base_url.rstrip('/')}{path}"
        return self.sender(
            method=method,
            url=url,
            headers=self._headers(extra),
            json=json_body,
            params=params,
            timeout=self.timeout_seconds,
        )


def _new_idempotency_key() -> str:
    return str(uuid.uuid4())


class _Resource(Protocol):
    transport: _Transport


@dataclass(slots=True)
class _Workspaces:
    transport: _Transport

    def create(
        self,
        *,
        name: str,
        application_type: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            "/api/v1/workspaces",
            json_body={"name": name, "application_type": application_type},
            idempotency_key=idempotency_key or _new_idempotency_key(),
        )

    def get(self, workspace_id: str) -> dict[str, Any]:
        return self.transport.request(
            "GET", f"/api/v1/workspaces/{workspace_id}"
        )

    def set_policy(
        self,
        workspace_id: str,
        *,
        source_yaml: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.transport.request(
            "PUT",
            f"/api/v1/workspaces/{workspace_id}/policy",
            json_body={"source_yaml": source_yaml, "activate": True},
            idempotency_key=idempotency_key or _new_idempotency_key(),
        )


@dataclass(slots=True)
class _TestRuns:
    transport: _Transport

    def create(
        self,
        *,
        workspace_id: str,
        repository: str,
        pull_number: int,
        head_sha: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            "/api/v1/test-runs",
            json_body={
                "workspace_id": workspace_id,
                "repository": repository,
                "pull_number": pull_number,
                "head_sha": head_sha,
            },
            idempotency_key=idempotency_key or _new_idempotency_key(),
        )

    def get(self, run_id: str) -> dict[str, Any]:
        return self.transport.request("GET", f"/api/v1/test-runs/{run_id}")

    def failures(self, run_id: str) -> dict[str, Any]:
        return self.transport.request(
            "GET", f"/api/v1/test-runs/{run_id}/failures"
        )


@dataclass(slots=True)
class _Approvals:
    transport: _Transport

    def list(
        self,
        *,
        state: str | None = None,
        workspace_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if state is not None:
            params["state"] = state
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        return self.transport.request(
            "GET", "/api/v1/approvals", params=params
        )

    def approve(
        self, request_id: str, *, comment: str | None = None
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            f"/api/v1/approvals/{request_id}/approve",
            json_body={"comment": comment},
        )

    def reject(
        self, request_id: str, *, comment: str | None = None
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            f"/api/v1/approvals/{request_id}/reject",
            json_body={"comment": comment},
        )


@dataclass(slots=True)
class _Usage:
    transport: _Transport

    def summary(
        self,
        *,
        workspace_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        return self.transport.request(
            "GET", "/api/v1/usage/summary", params=params
        )


@dataclass(slots=True)
class AQAOClient:
    """Synchronous Agentic QA Orchestrator SDK client.

    The constructor accepts a ``sender`` callable for testability —
    production callers leave it ``None`` and the client wires an
    httpx-backed sender lazily.
    """

    base_url: str
    token: str
    tenant_id: str
    role: str | None = None
    timeout_seconds: float = 30.0
    sender: Callable[..., dict[str, Any]] | None = None

    transport: _Transport = field(init=False)
    workspaces: _Workspaces = field(init=False)
    test_runs: _TestRuns = field(init=False)
    approvals: _Approvals = field(init=False)
    usage: _Usage = field(init=False)

    def __post_init__(self) -> None:
        sender = self.sender or _default_sender()
        self.transport = _Transport(
            base_url=self.base_url,
            token=self.token,
            tenant_id=self.tenant_id,
            role=self.role,
            timeout_seconds=self.timeout_seconds,
            sender=sender,
        )
        self.workspaces = _Workspaces(transport=self.transport)
        self.test_runs = _TestRuns(transport=self.transport)
        self.approvals = _Approvals(transport=self.transport)
        self.usage = _Usage(transport=self.transport)


@dataclass(slots=True)
class AsyncAQAOClient(AQAOClient):
    """Async variant — same surface, awaitable methods.

    Phase-5 ships the same shape as :class:`AQAOClient` so callers
    can swap by changing the import; the async-specific httpx wiring
    lands when the openapi-python-client codegen does.
    """


def _default_sender() -> Callable[..., dict[str, Any]]:
    """Lazy httpx-backed sender. Imported on first use so an SDK
    consumer that injects their own sender doesn't pay the import
    cost."""

    def _send(
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        json: dict[str, Any] | None,
        params: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        import httpx
        from aqao_sdk.errors import error_for_status

        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method, url, headers=headers, json=json, params=params
            )
        if response.status_code >= 400:
            payload: dict[str, Any] = {}
            try:
                payload = response.json()
            except ValueError:
                payload = {"detail": response.text}
            retry_after: float | None = None
            if response.status_code == 429:
                raw = response.headers.get("Retry-After")
                if raw is not None:
                    try:
                        retry_after = float(raw)
                    except ValueError:
                        retry_after = None
            raise error_for_status(
                status_code=response.status_code,
                message=str(payload.get("detail", response.text or "request failed")),
                trace_id=response.headers.get("X-AQAO-Trace-Id"),
                details=payload.get("errors"),
                retry_after_seconds=retry_after,
            )
        if not response.content:
            return {}
        return response.json()

    return _send


__all__ = ["AsyncAQAOClient", "AQAOClient"]
