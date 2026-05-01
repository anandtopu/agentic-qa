"""Integration tests for /api/v1/workspaces/{id}/policy — Story 1.1.3.

Confirms the AC most explicitly: a policy violating the schema returns
422 with field-level errors. Also exercises versioning and activation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from aqao_api.auth.context import TENANT_HEADER, USER_HEADER
from aqao_api.main import create_app
from aqao_api.policies import DEFAULT_POLICY_YAML

pytestmark = pytest.mark.integration

INVALID_POLICY = """
policy:
  allow_write_operations: false
  max_cost_usd_per_run: -1
  max_runtime_minutes: 9999
  require_approval_for:
    - destructive_sql
    - made_up_gate
"""


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


async def _create_workspace(client: httpx.AsyncClient, tenant_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": "Payments", "application_type": "web_api"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_put_default_policy_returns_200_and_version_1(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/policy",
        json={"source_yaml": DEFAULT_POLICY_YAML},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["active"] is True


@pytest.mark.asyncio
async def test_put_invalid_policy_returns_422_with_field_errors(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/policy",
        json={"source_yaml": INVALID_POLICY},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "policy validation failed"
    locations = [tuple(e["loc"]) for e in body["errors"]]
    assert ("max_cost_usd_per_run",) in locations
    assert ("max_runtime_minutes",) in locations


@pytest.mark.asyncio
async def test_put_malformed_yaml_returns_422_with_position(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/policy",
        json={"source_yaml": "policy: [unterminated"},
        headers=_headers(tenant_id),
    )
    assert response.status_code == 422
    err = response.json()["errors"][0]
    assert err["type"] == "yaml_parse_error"


@pytest.mark.asyncio
async def test_get_active_returns_404_until_set(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)
    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/policy",
        headers=_headers(tenant_id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_versioning_and_activation_round_trip(
    client: httpx.AsyncClient, tenant_id: uuid.UUID
) -> None:
    workspace_id = await _create_workspace(client, tenant_id)

    v1 = await client.put(
        f"/api/v1/workspaces/{workspace_id}/policy",
        json={"source_yaml": DEFAULT_POLICY_YAML},
        headers=_headers(tenant_id),
    )
    v2_yaml = DEFAULT_POLICY_YAML.replace(
        "max_cost_usd_per_run: 5.00", "max_cost_usd_per_run: 10.00"
    )
    v2 = await client.put(
        f"/api/v1/workspaces/{workspace_id}/policy",
        json={"source_yaml": v2_yaml},
        headers=_headers(tenant_id),
    )
    assert v1.json()["version"] == 1
    assert v2.json()["version"] == 2
    assert v2.json()["active"] is True

    history = await client.get(
        f"/api/v1/workspaces/{workspace_id}/policy/history",
        headers=_headers(tenant_id),
    )
    versions = [v["version"] for v in history.json()["versions"]]
    assert versions == [2, 1]

    activate = await client.post(
        f"/api/v1/workspaces/{workspace_id}/policy/activate/1",
        headers=_headers(tenant_id),
    )
    assert activate.status_code == 200
    assert activate.json()["version"] == 1
    assert activate.json()["active"] is True

    active = await client.get(
        f"/api/v1/workspaces/{workspace_id}/policy",
        headers=_headers(tenant_id),
    )
    assert active.json()["version"] == 1
