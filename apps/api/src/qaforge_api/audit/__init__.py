"""Audit log signing + verification — Story 2.4.1.

Phase 1 ships the unsigned ``audit_events`` table; Phase 2 layers on
HMAC-SHA256 signatures so a row that's been mutated outside the
:class:`AuditService` insert path can be detected by a verifier sweep.

The signing key lives in ``QAFORGE_AUDIT_HMAC_KEY`` (Settings). Phase 1
rows have NULL signatures and are reported as ``unsigned`` (distinct
from ``tampered``) so the upgrade is additive — no backfill required.
"""

from qaforge_api.audit.signing import (
    AUDIT_SIGNATURE_VERSION,
    AuditSignatureStatus,
    canonical_payload,
    compute_signature,
    verify_signature,
)

__all__ = [
    "AUDIT_SIGNATURE_VERSION",
    "AuditSignatureStatus",
    "canonical_payload",
    "compute_signature",
    "verify_signature",
]
