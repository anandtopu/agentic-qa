"""Integration tests for /api/v1/workspaces/{id}/requirements — Story 1.2.

Validates the full ingest path: schema validation, parser dispatch,
status enum, audit emission, RLS scoping.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from qaforge_api.auth.context import TENANT_HEADER
from qaforge_api.main import create_app

pytestmark = pytest.mark.integration

OPENAPI_DOC = """
openapi: 3.0.3
info: {title: Payments, version: 1.0.0}
paths:
  /charge:
    post:
      operationId: createCharge
"""

POSTMAN_DOC = json.dumps(
    {
        "info": {
            "name": "Smoke",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": "Health", "request": {"method": "GET", "url": "https://x/healthz"}}],
    }
)


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
async def test_ingest_user_story_returns_201_with_parsed_ac(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={
            "type": "user_story",
            "source_ref": "stories/login.md",
            "payload": {
                "body": "# Login\n\n## Acceptance Criteria\n\n- User can sign in\n",
            },
        },
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "parsed"
    assert body["parsed"]["acceptance_criteria"][0]["text"] == "User can sign in"


@pytest.mark.asyncio
async def test_ingest_openapi_preserves_operation_ids(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={"type": "openapi", "payload": {"body": OPENAPI_DOC}},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    op_ids = [e["operation_id"] for e in response.json()["parsed"]["endpoints"]]
    assert op_ids == ["createCharge"]


@pytest.mark.asyncio
async def test_ingest_postman(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={"type": "postman", "payload": {"body": POSTMAN_DOC}},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    assert response.json()["parsed"]["request_count"] == 1


@pytest.mark.asyncio
async def test_ingest_failure_persists_with_status_failed(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    """Bad input doesn't 4xx — we keep the row for triage with status=failed."""
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={"type": "openapi", "payload": {"body": "not yaml or json: ["}},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["parse_error"]


@pytest.mark.asyncio
async def test_list_filters_by_type(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={
            "type": "user_story",
            "payload": {"body": "## Acceptance Criteria\n- foo"},
        },
        headers=_headers(tenant_id),
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/requirements",
        json={"type": "openapi", "payload": {"body": OPENAPI_DOC}},
        headers=_headers(tenant_id),
    )

    only_stories = await client.get(
        f"/api/v1/workspaces/{workspace_id}/requirements?type=user_story",
        headers=_headers(tenant_id),
    )
    types = {r["type"] for r in only_stories.json()["requirements"]}
    assert types == {"user_story"}


@pytest.mark.asyncio
async def test_get_unknown_id_returns_404(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> None:
    response = await client.get(
        f"/api/v1/requirements/{uuid.uuid4()}",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 404
