"""Unit tests for the auth header context.

The HTTP roundtrip is exercised in the integration tests; here we just
verify header parsing, UUID validation, and the require/optional split.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi import HTTPException

from aqao_api.auth.context import (
    get_request_context,
    require_request_context,
)


def test_get_request_context_returns_none_without_tenant_header() -> None:
    result = asyncio.run(get_request_context(None, None, None, None))
    assert result is None


def test_get_request_context_parses_valid_uuids() -> None:
    tenant = "00000000-0000-0000-0000-00000000000a"
    user = "00000000-0000-0000-0000-00000000000b"
    result = asyncio.run(
        get_request_context(
            x_aqao_tenant_id=tenant,
            x_aqao_user_id=user,
            x_aqao_role=None,
            x_aqao_trace_id="trace-1",
        )
    )
    assert result is not None
    assert result.tenant_id == UUID(tenant)
    assert result.user_id == UUID(user)
    assert result.correlation_id == "trace-1"


def test_get_request_context_rejects_invalid_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_request_context("not-a-uuid", None, None, None))
    assert exc_info.value.status_code == 400


def test_require_request_context_401s_when_missing() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_request_context(None, None, None, None, None))
    assert exc_info.value.status_code == 401
