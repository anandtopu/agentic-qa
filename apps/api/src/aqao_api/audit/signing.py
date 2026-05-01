"""HMAC-SHA256 signing for audit_events rows.

Two stable functions:

* :func:`compute_signature` — used by ``AuditService.record`` on insert.
* :func:`verify_signature` — used by query / export to mark rows
  ``signed_ok`` / ``tampered`` / ``unsigned``.

The canonical payload is a deterministic JSON serialisation of the
fields a tamper would change: ``id``, ``tenant_id``, ``actor_user_id``,
``action``, ``resource_type``, ``resource_id``, ``payload``,
``correlation_id``, and ``created_at`` (ISO-8601, UTC, microsecond
precision). Anything outside this set (e.g. database-managed columns)
is intentionally excluded so server-side housekeeping doesn't break
verification.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

AUDIT_SIGNATURE_VERSION = "v1"
"""Signature schema version — prefixed onto every digest so a future
field change can be rolled out without invalidating every prior row."""

_VERSION_PREFIX = f"{AUDIT_SIGNATURE_VERSION}:"


class AuditSignatureStatus(StrEnum):
    SIGNED_OK = "signed_ok"
    TAMPERED = "tampered"
    UNSIGNED = "unsigned"
    NO_KEY_CONFIGURED = "no_key_configured"


def canonical_payload(
    *,
    audit_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    payload: dict[str, Any] | None,
    correlation_id: str | None,
    created_at: datetime,
) -> bytes:
    """Return the deterministic byte-string we sign.

    Determinism is enforced by ``json.dumps(..., sort_keys=True,
    separators=(',', ':'))`` plus explicit string conversion of UUIDs
    and datetimes. Two semantically-equal events produce the same
    bytes regardless of dict insertion order.
    """
    document = {
        "id": str(audit_id),
        "tenant_id": str(tenant_id),
        "actor_user_id": str(actor_user_id) if actor_user_id is not None else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "created_at": _iso_utc(created_at),
        "version": AUDIT_SIGNATURE_VERSION,
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_signature(secret: str, *, body: bytes) -> str:
    """Return ``v1:<base64-hmac-sha256>`` for ``body``."""
    if not secret:
        raise ValueError("audit HMAC secret must be non-empty")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return _VERSION_PREFIX + base64.b64encode(digest).decode("ascii")


def verify_signature(
    secret: str | None,
    *,
    body: bytes,
    stored_signature: str | None,
) -> AuditSignatureStatus:
    """Return the verification status of one row."""
    if stored_signature is None:
        return AuditSignatureStatus.UNSIGNED
    if not secret:
        return AuditSignatureStatus.NO_KEY_CONFIGURED
    if not stored_signature.startswith(_VERSION_PREFIX):
        # A row signed under a different version — treat as tampered for
        # safety; a future ``verify_signature_legacy`` can recognise
        # known prior schemas.
        return AuditSignatureStatus.TAMPERED
    expected = compute_signature(secret, body=body)
    return (
        AuditSignatureStatus.SIGNED_OK
        if hmac.compare_digest(expected, stored_signature)
        else AuditSignatureStatus.TAMPERED
    )


def _iso_utc(value: datetime) -> str:
    """Render a datetime as ISO-8601 with microsecond precision in UTC."""
    if value.tzinfo is None:
        return value.isoformat(timespec="microseconds") + "+00:00"
    return value.astimezone(value.tzinfo).isoformat(timespec="microseconds")
