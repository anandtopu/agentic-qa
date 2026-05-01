"""GitHub webhook signature verification + tenant resolution.

GitHub signs the request body with HMAC-SHA256 keyed by the webhook
secret and sends the digest as ``X-Hub-Signature-256: sha256=<hex>``.
We verify with a constant-time compare; mismatched or absent signatures
yield 401 — never 4xx with details that would help an attacker probe.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_api.db.models import Repository, Workspace

SIGNATURE_HEADER = "X-Hub-Signature-256"
EVENT_HEADER = "X-GitHub-Event"
DELIVERY_HEADER = "X-GitHub-Delivery"


@dataclass(frozen=True, slots=True)
class WebhookResolution:
    workspace_id: object  # uuid.UUID — typed loosely to avoid cyclic imports
    tenant_id: object
    repository_id: object


def verify_signature(*, secret: str, body: bytes, header_value: str | None) -> bool:
    """Return True iff ``header_value`` matches the HMAC over ``body``."""
    if not secret:
        return False
    if not header_value or not header_value.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    provided = header_value.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


def resolve_workspace_for_repo(session: Session, *, full_name: str) -> WebhookResolution | None:
    """Find the workspace that has an active link for ``full_name``.

    Webhook paths run *without* RLS context (no JWT, no tenant header) —
    the caller should set ``app.current_tenant_id`` from the resolved
    tenant before any further DB reads/writes. We use a privileged
    session (or a SET LOCAL bypass) to do this lookup.
    """
    stmt = (
        select(Repository, Workspace)
        .join(Workspace, Workspace.id == Repository.workspace_id)
        .where(
            Repository.full_name == full_name,
            Repository.unlinked_at.is_(None),
        )
        .limit(1)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    repository, workspace = row
    return WebhookResolution(
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
        repository_id=repository.id,
    )
