"""Integration tests for /api/v1/workspaces/{id}/repository — Story 1.1.2."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from qaforge_api.auth.context import TENANT_HEADER, USER_HEADER
from qaforge_api.integrations.github.client import (
    get_github_client,
    reset_github_client_cache,
)
from qaforge_api.integrations.github.stub_client import StubGitHubClient
from qaforge_api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def stub_github() -> Iterator[StubGitHubClient]:
    stub = StubGitHubClient()
    reset_github_client_cache()
    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: stub
    yield stub
    app.dependency_overrides.clear()
    reset_github_client_cache()


@pytest.fixture
async def client(stub_github: StubGitHubClient) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: stub_github
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _headers(tenant_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, str]:
    headers = {TENANT_HEADER: str(tenant_id)}
    if user_id is not None:
        headers[USER_HEADER] = str(user_id)
    return headers


async def _create_workspace(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "Payments", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_link_returns_201_with_metadata(
    client: httpx.AsyncClient,
    tenant_id: uuid.UUID,
    stub_github: StubGitHubClient,
) -> None:
    stub_github.register_repository(
        installation_id=42, full_name="org/svc", default_branch="develop"
    )
    workspace_id = await _create_workspace(client, tenant_id)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json={"installation_id": 42, "full_name": "org/svc"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "org/svc"
    assert body["default_branch"] == "develop"
    assert body["unlinked_at"] is None


@pytest.mark.asyncio
async def test_link_invalid_full_name_returns_422(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json={"installation_id": 1, "full_name": "bad-name"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_link_unknown_workspace_returns_404(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    response = await client.post(
        f"/api/v1/workspaces/{uuid.uuid4()}/repository",
        json={"installation_id": 1, "full_name": "org/repo"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_link_twice_returns_409(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    payload = {"installation_id": 1, "full_name": "org/repo"}
    first = await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json=payload,
        headers=_headers(tenant_id),
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json=payload,
        headers=_headers(tenant_id),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_returns_active_repository(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json={"installation_id": 1, "full_name": "org/repo"},
        headers=_headers(tenant_id),
    )
    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/repository",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "org/repo"


@pytest.mark.asyncio
async def test_get_when_unlinked_returns_404(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/repository",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_unlinks_and_records_revoke(
    client: httpx.AsyncClient,
    tenant_id: uuid.UUID,
    stub_github: StubGitHubClient,
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/repository",
        json={"installation_id": 99, "full_name": "org/repo"},
        headers=_headers(tenant_id),
    )
    response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/repository",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 200
    assert response.json()["unlinked_at"] is not None
    assert 99 in stub_github.revoked_installations
