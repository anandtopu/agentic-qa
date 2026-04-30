"""Tests for the tenant-isolation alert hook — Story 3.1.1.

PRD Phase-3 AC: cross-tenant access attempts return 404 (not 403) and
are alerted. The 404 part is enforced by RLS in production and by
the service layer's ``ResourceNotFoundError`` everywhere; this suite
covers the alert hook.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from qaforge_api.auth import emit_resource_miss
from qaforge_api.auth.context import RequestContext


def _ctx(**overrides: Any) -> RequestContext:
    base: dict[str, Any] = {
        "tenant_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        "user_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        "correlation_id": "trace-1",
    }
    base.update(overrides)
    return RequestContext(**base)


def test_emit_resource_miss_logs_structured_event() -> None:
    with structlog.testing.capture_logs() as captured:
        emit_resource_miss(
            context=_ctx(),
            resource_type="workspace",
            resource_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        )
    assert len(captured) == 1
    entry = captured[0]
    assert entry["event"] == "tenant_isolation.resource_miss"
    assert entry["resource_type"] == "workspace"
    assert entry["tenant_id"].startswith("aaaaaaaa")
    assert entry["log_level"] == "info"


def test_emit_resource_miss_handles_missing_user() -> None:
    with structlog.testing.capture_logs() as captured:
        emit_resource_miss(
            context=_ctx(user_id=None),
            resource_type="approval_request",
            resource_id="missing-id",
        )
    # Anonymous probes (no user_id) are exactly the cross-tenant
    # scenario we want logged — the call must not raise and must
    # surface ``actor_user_id=None``.
    assert captured[0]["actor_user_id"] is None
    assert captured[0]["resource_id"] == "missing-id"
