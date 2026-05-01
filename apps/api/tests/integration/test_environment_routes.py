"""Integration tests for /api/v1/workspaces/{id}/environments — Story 1.1.3."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from aqao_api.auth.context import TENANT_HEADER
from aqao_api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _headers(tenant_id: uuid.UUID) -> dict[str, str]:
    return {TENANT_HEADER: str(tenant_id)}


async def _create_workspace(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "Payments", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_upsert_creates_environment(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/environments/staging",
        json={
            "name": "staging",
            "base_url": "https://staging.payments.example.com",
            "is_production": False,
            "variables": {"FEATURE_FLAG_X": "on"},
        },
        headers=_headers(tenant_id),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "staging"
    assert body["variables"]["FEATURE_FLAG_X"] == "on"


@pytest.mark.asyncio
async def test_upsert_path_body_name_mismatch_is_400(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/environments/staging",
        json={"name": "production", "is_production": True, "variables": {}},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_returns_envs_alphabetically(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    for env in ("staging", "dev", "prod"):
        await client.put(
            f"/api/v1/workspaces/{workspace_id}/environments/{env}",
            json={"name": env, "is_production": env == "prod", "variables": {}},
            headers=_headers(tenant_id),
        )
    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/environments",
        headers=_headers(tenant_id),
    )
    names = [e["name"] for e in response.json()["environments"]]
    assert names == ["dev", "prod", "staging"]


@pytest.mark.asyncio
async def test_delete_removes_environment(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/environments/dev",
        json={"name": "dev", "is_production": False, "variables": {}},
        headers=_headers(tenant_id),
    )
    delete = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/environments/dev",
        headers=_headers(tenant_id),
    )
    assert delete.status_code == 204

    fetch = await client.get(
        f"/api/v1/workspaces/{workspace_id}/environments/dev",
        headers=_headers(tenant_id),
    )
    assert fetch.status_code == 404
