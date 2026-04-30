"""Integration tests for /api/v1/webhooks/github — Story 1.2.1.

Posts an HMAC-signed webhook body and asserts the requirement is
ingested under the correct workspace and tenant.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from qaforge_api.auth.context import TENANT_HEADER
from qaforge_api.config import get_settings
from qaforge_api.integrations.github.client import (
    get_github_client,
    reset_github_client_cache,
)
from qaforge_api.integrations.github.stub_client import StubGitHubClient
from qaforge_api.main import create_app

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-secret"


@pytest.fixture
def stub_github() -> StubGitHubClient:
    reset_github_client_cache()
    return StubGitHubClient()


@pytest.fixture
async def client(
    stub_github: StubGitHubClient, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("QAFORGE_GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: stub_github
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    get_settings.cache_clear()  # type: ignore[attr-defined]


def _sign(body: bytes) -> str:
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def _link_repo(client: httpx.AsyncClient, tenant_id: uuid.UUID, full_name: str) -> uuid.UUID:
    ws = await client.post(
        "/api/v1/workspaces",
        json={"name": "Payments", "application_type": "web_api"},
        headers={TENANT_HEADER: str(tenant_id)},
    )
    workspace_id = uuid.UUID(ws.json()["id"])
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json={"installation_id": 42, "full_name": full_name},
        headers={TENANT_HEADER: str(tenant_id)},
    )
    return workspace_id


@pytest.mark.asyncio
async def test_signed_pull_request_event_ingests_requirement(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _link_repo(client, tenant_id, "qaforge/sample")

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "title": "Add payment",
            "body": "",
            "head": {"sha": "abc123", "ref": "feature/pay"},
            "base": {"ref": "main", "repo": {"full_name": "qaforge/sample"}},
        },
        "repository": {"full_name": "qaforge/sample"},
    }
    body = json.dumps(payload).encode("utf-8")

    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "test-delivery-1",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 202
    body_json = response.json()
    assert body_json["status"] == "accepted"

    listing = await client.get(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        headers={TENANT_HEADER: str(tenant_id)},
    )
    types = [r["type"] for r in listing.json()["requirements"]]
    assert "pr_diff" in types


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/webhooks/github",
        content=b"{}",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=00",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_signature_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/webhooks/github",
        content=b"{}",
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_pr_event_acks_without_ingest(
    client: httpx.AsyncClient,
) -> None:
    body = b"{}"
    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_pr_event_for_unlinked_repo_returns_no_workspace(
    client: httpx.AsyncClient,
) -> None:
    payload = {
        "action": "opened",
        "pull_request": {"number": 1, "head": {"sha": "x"}, "base": {"ref": "main"}},
        "repository": {"full_name": "nobody/unlinked"},
    }
    body = json.dumps(payload).encode("utf-8")
    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "no_workspace"
