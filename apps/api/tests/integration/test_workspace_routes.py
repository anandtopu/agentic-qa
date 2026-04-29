"""Integration tests for /api/v1/workspaces.

Full HTTP round-trip with header-based tenant scoping. Hits real
Postgres for RLS verification.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from qaforge_api.auth.context import TENANT_HEADER, USER_HEADER
from qaforge_api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _headers(tenant_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, str]:
    headers = {TENANT_HEADER: str(tenant_id)}
    if user_id is not None:
        headers[USER_HEADER] = str(user_id)
    return headers


@pytest.mark.asyncio
async def test_create_workspace_returns_201(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "Payments", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Payments"
    assert body["tenant_id"] == str(tenant_id)
    assert body["default_branch"] == "main"


@pytest.mark.asyncio
async def test_create_without_tenant_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "X", "application_type": "web_api"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_name_returns_409(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    payload = {"name": "Dup", "application_type": "web_api"}
    first = await client.post("/api/v1/workspaces", json=payload, headers=_headers(tenant_id))
    assert first.status_code == 201
    second = await client.post("/api/v1/workspaces", json=payload, headers=_headers(tenant_id))
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_invalid_application_type_returns_422(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "X", "application_type": "alien"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_returns_only_caller_tenant_workspaces(
    client: httpx.AsyncClient, tenant_id: uuid.UUID, other_tenant_id: uuid.UUID
) -> None:
    await client.post(
        "/api/v1/workspaces",
        json={"name": "Mine", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    await client.post(
        "/api/v1/workspaces",
        json={"name": "Theirs", "application_type": "web_api"},
        headers=_headers(other_tenant_id),
    )

    mine = await client.get("/api/v1/workspaces", headers=_headers(tenant_id))
    assert mine.status_code == 200
    names = [w["name"] for w in mine.json()["workspaces"]]
    assert names == ["Mine"]


@pytest.mark.asyncio
async def test_get_unknown_workspace_returns_404(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    response = await client.get(
        f"/api/v1/workspaces/{uuid.uuid4()}",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_cross_tenant_returns_404(
    client: httpx.AsyncClient, tenant_id: uuid.UUID, other_tenant_id: uuid.UUID
) -> None:
    create = await client.post(
        "/api/v1/workspaces",
        json={"name": "Mine", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    workspace_id = create.json()["id"]
    snoop = await client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_headers(other_tenant_id),
    )
    assert snoop.status_code == 404


@pytest.mark.asyncio
async def test_patch_partial_update(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    create = await client.post(
        "/api/v1/workspaces",
        json={"name": "X", "application_type": "web_api", "description": "old"},
        headers=_headers(tenant_id),
    )
    workspace_id = create.json()["id"]
    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"description": "new"},
        headers=_headers(tenant_id),
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["description"] == "new"
    assert body["name"] == "X"  # unchanged


@pytest.mark.asyncio
async def test_patch_explicit_null_clears_field(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    create = await client.post(
        "/api/v1/workspaces",
        json={
            "name": "X",
            "application_type": "web_api",
            "description": "to be cleared",
        },
        headers=_headers(tenant_id),
    )
    workspace_id = create.json()["id"]
    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"description": None},
        headers=_headers(tenant_id),
    )
    assert patched.status_code == 200
    assert patched.json()["description"] is None
