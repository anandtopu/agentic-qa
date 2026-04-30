"""Unit tests for the audit HMAC signing module — Story 2.4.1."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from qaforge_api.audit.signing import (
    AUDIT_SIGNATURE_VERSION,
    AuditSignatureStatus,
    canonical_payload,
    compute_signature,
    verify_signature,
)

_ID = UUID("11111111-2222-3333-4444-555555555555")
_TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_CREATED_AT = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
_SECRET = "topsecret-rotate-me"


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "audit_id": _ID,
        "tenant_id": _TENANT,
        "actor_user_id": _USER,
        "action": "workspace.create",
        "resource_type": "workspace",
        "resource_id": "ws-42",
        "payload": {"name": "Payments", "k": 1},
        "correlation_id": "trace-1",
        "created_at": _CREATED_AT,
    }
    base.update(overrides)
    return base


def test_canonical_payload_is_deterministic_across_dict_orders() -> None:
    a = canonical_payload(**_payload(payload={"k": 1, "name": "Payments"}))  # type: ignore[arg-type]
    b = canonical_payload(**_payload(payload={"name": "Payments", "k": 1}))  # type: ignore[arg-type]
    assert a == b


def test_canonical_payload_is_utf8_bytes() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    assert isinstance(body, bytes)
    text = body.decode("utf-8")
    assert '"action":"workspace.create"' in text
    assert '"version":"v1"' in text


def test_compute_signature_starts_with_version_prefix() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    assert sig.startswith(f"{AUDIT_SIGNATURE_VERSION}:")


def test_round_trip_verifies_signed_ok() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    status = verify_signature(_SECRET, body=body, stored_signature=sig)
    assert status is AuditSignatureStatus.SIGNED_OK


def test_unsigned_row_is_distinguished_from_tampered() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    status = verify_signature(_SECRET, body=body, stored_signature=None)
    assert status is AuditSignatureStatus.UNSIGNED


def test_tampered_payload_fails_verification() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    tampered_body = canonical_payload(**_payload(action="workspace.delete"))  # type: ignore[arg-type]
    status = verify_signature(_SECRET, body=tampered_body, stored_signature=sig)
    assert status is AuditSignatureStatus.TAMPERED


def test_tampered_payload_field_action() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    body_modified = canonical_payload(**_payload(payload={"name": "Other"}))  # type: ignore[arg-type]
    assert (
        verify_signature(_SECRET, body=body_modified, stored_signature=sig)
        is AuditSignatureStatus.TAMPERED
    )


def test_wrong_secret_fails_verification() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    assert (
        verify_signature("different-key", body=body, stored_signature=sig)
        is AuditSignatureStatus.TAMPERED
    )


def test_missing_key_returns_no_key_status() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    sig = compute_signature(_SECRET, body=body)
    assert (
        verify_signature(None, body=body, stored_signature=sig)
        is AuditSignatureStatus.NO_KEY_CONFIGURED
    )
    assert (
        verify_signature("", body=body, stored_signature=sig)
        is AuditSignatureStatus.NO_KEY_CONFIGURED
    )


def test_signature_with_unknown_version_treated_as_tampered() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    bogus = "v99:" + "A" * 44
    assert (
        verify_signature(_SECRET, body=body, stored_signature=bogus)
        is AuditSignatureStatus.TAMPERED
    )


def test_compute_signature_rejects_empty_secret() -> None:
    body = canonical_payload(**_payload())  # type: ignore[arg-type]
    try:
        compute_signature("", body=body)
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_payload_with_none_actor_and_resource_serialises() -> None:
    body = canonical_payload(
        **_payload(actor_user_id=None, resource_id=None, correlation_id=None)  # type: ignore[arg-type]
    )
    text = body.decode("utf-8")
    assert '"actor_user_id":null' in text
    assert '"resource_id":null' in text
    assert '"correlation_id":null' in text
