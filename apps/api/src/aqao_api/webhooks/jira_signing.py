"""Jira webhook signature verification — Story 4.4.

Jira ships HMAC-SHA256 webhook signatures via the
``X-Hub-Signature-256`` header (same shape as GitHub's, just a
different secret). Verification is a constant-time HMAC compare
identical to ``aqao_api.webhooks.github.verify_signature``;
factored into its own module so the secret-resolution path can stay
provider-aware.
"""

from __future__ import annotations

import hashlib
import hmac

JIRA_SIGNATURE_HEADER = "X-Hub-Signature-256"


def verify_jira_signature(*, secret: str, body: bytes, header_value: str | None) -> bool:
    """Return True iff the X-Hub-Signature-256 header matches the
    HMAC-SHA256 of the request body keyed by the workspace's Jira
    webhook secret.

    Returns False on any malformed input — callers should treat False
    as a 401, never as "skip verification".
    """
    if header_value is None or not secret:
        return False
    if not header_value.startswith("sha256="):
        return False
    provided = header_value[len("sha256=") :]
    expected = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


__all__ = ["JIRA_SIGNATURE_HEADER", "verify_jira_signature"]
