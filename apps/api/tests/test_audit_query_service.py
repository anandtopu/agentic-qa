"""Unit tests for the AuditQueryService export helpers — Story 2.4.2.

The DB-backed query path is exercised by the integration suite (Postgres
+ RLS); here we test the in-process helpers (CSV/JSON shaping +
verification status mapping) that don't touch a session.
"""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from qaforge_api.audit.signing import AuditSignatureStatus
from qaforge_api.services.audit_query import (
    AuditQueryService,
    VerifiedAuditEvent,
)


@dataclass(slots=True)
class _StubEvent:
    """Lightweight stand-in for the AuditEvent ORM row."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    payload: dict[str, Any]
    correlation_id: str | None
    signature: str | None
    created_at: datetime


def _event(**overrides: Any) -> _StubEvent:
    base = {
        "id": uuid.UUID("11111111-2222-3333-4444-555555555555"),
        "tenant_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        "actor_user_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        "action": "workspace.create",
        "resource_type": "workspace",
        "resource_id": "ws-42",
        "payload": {"name": "Payments"},
        "correlation_id": "trace-1",
        "signature": "v1:abc==",
        "created_at": datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return _StubEvent(**base)


def _verified(
    event: _StubEvent, status: AuditSignatureStatus = AuditSignatureStatus.SIGNED_OK
) -> VerifiedAuditEvent:
    return VerifiedAuditEvent(event=event, status=status)  # type: ignore[arg-type]


def _service() -> AuditQueryService:
    return AuditQueryService(session=None, hmac_key="test-key")  # type: ignore[arg-type]


def test_to_dict_includes_signature_status_and_payload() -> None:
    ve = _verified(_event())
    out = ve.to_dict()
    assert out["signature_status"] == "signed_ok"
    assert out["payload"] == {"name": "Payments"}
    assert out["actor_user_id"].startswith("bbbbbbbb")


def test_csv_export_has_expected_headers_and_one_row() -> None:
    csv_text = _service().export_csv([_verified(_event())])
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert len(rows) == 1
    row = rows[0]
    assert row["action"] == "workspace.create"
    assert row["signature_status"] == "signed_ok"
    # payload is JSON-serialised in CSV
    assert json.loads(row["payload"]) == {"name": "Payments"}


def test_json_export_round_trips() -> None:
    json_text = _service().export_json([_verified(_event())])
    parsed = json.loads(json_text)
    assert parsed[0]["action"] == "workspace.create"
    assert parsed[0]["signature_status"] == "signed_ok"


def test_unsigned_status_propagates_to_export() -> None:
    csv_text = _service().export_csv(
        [_verified(_event(signature=None), AuditSignatureStatus.UNSIGNED)]
    )
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows[0]["signature_status"] == "unsigned"


def test_tampered_status_propagates_to_export() -> None:
    csv_text = _service().export_csv(
        [_verified(_event(action="workspace.delete"), AuditSignatureStatus.TAMPERED)]
    )
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows[0]["signature_status"] == "tampered"
    assert rows[0]["action"] == "workspace.delete"


def test_stream_json_lines_emits_one_object_per_event() -> None:
    events = [_verified(_event()), _verified(_event(action="workspace.update"))]
    lines = list(_service().stream_json_lines(events))
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    actions = [p["action"] for p in parsed]
    assert actions == ["workspace.create", "workspace.update"]
