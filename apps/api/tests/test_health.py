from __future__ import annotations

import httpx
import pytest

from qaforge_api.middleware import TRACE_HEADER


@pytest.mark.asyncio
async def test_healthz_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_readyz_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_correlation_id_is_echoed_when_provided(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={TRACE_HEADER: "fixed-trace-id-123"})
    assert response.headers[TRACE_HEADER] == "fixed-trace-id-123"


@pytest.mark.asyncio
async def test_correlation_id_is_generated_when_missing(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert TRACE_HEADER in response.headers
    assert len(response.headers[TRACE_HEADER]) >= 16


@pytest.mark.asyncio
async def test_openapi_contains_health_routes(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/healthz" in paths
    assert "/readyz" in paths
