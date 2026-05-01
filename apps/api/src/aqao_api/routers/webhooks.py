"""Inbound webhook routes — Story 1.2.1 (GitHub PR ingestion).

GitHub webhooks bypass header-based tenant auth: the security model is
HMAC signature verification + repo-to-workspace lookup. Once the workspace
is resolved we open a tenant-scoped session manually (the standard
``require_request_context`` dependency would 401 since the request has no
tenant header).
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from aqao_api.auth.context import RequestContext
from aqao_api.config import get_settings
from aqao_api.db.models.requirement import RequirementType
from aqao_api.db.session import get_sessionmaker
from aqao_api.services.requirement import RequirementService
from aqao_api.webhooks.github import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
    resolve_workspace_for_repo,
    verify_signature,
)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
_log = structlog.get_logger("aqao_api.webhooks.github")

_PR_ACTIONS = frozenset({"opened", "synchronize", "reopened", "edited", "ready_for_review"})


@router.post(
    "/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub webhook receiver (HMAC-verified)",
)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias=SIGNATURE_HEADER),
    x_github_event: str | None = Header(default=None, alias=EVENT_HEADER),
    x_github_delivery: str | None = Header(default=None, alias=DELIVERY_HEADER),
) -> dict[str, str]:
    body_bytes = await request.body()
    settings = get_settings()
    secret = (
        settings.github_webhook_secret.get_secret_value()
        if settings.github_webhook_secret is not None
        else ""
    )

    if not verify_signature(secret=secret, body=body_bytes, header_value=x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing webhook signature",
        )

    if x_github_event != "pull_request":
        # Acknowledge other events (push, ping, etc.) but don't ingest.
        _log.info(
            "github.webhook.skipped",
            event=x_github_event,
            delivery=x_github_delivery,
        )
        return {"status": "ignored", "event": x_github_event or ""}

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="webhook body is not valid JSON",
        ) from exc

    action = payload.get("action")
    if action not in _PR_ACTIONS:
        return {"status": "ignored", "action": str(action)}

    repo = (payload.get("repository") or {}).get("full_name")
    if not isinstance(repo, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository.full_name missing",
        )

    factory = get_sessionmaker()
    session = factory()
    try:
        # Webhook context has no tenant yet — privileged lookup.
        # RLS would need ``app.current_tenant_id`` set; the session role
        # in dev is the same as the migrate role, so this read succeeds.
        # Phase 3 hardening will introduce a dedicated webhook DB role.
        resolution = resolve_workspace_for_repo(session, full_name=repo)
        if resolution is None:
            return {"status": "no_workspace", "repository": repo}

        session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(resolution.tenant_id)},
        )

        context = RequestContext(
            tenant_id=resolution.tenant_id,  # type: ignore[arg-type]
            user_id=None,
            correlation_id=x_github_delivery,
        )
        service = RequirementService(session)
        row = service.ingest(
            workspace_id=resolution.workspace_id,  # type: ignore[arg-type]
            type=RequirementType.PR_DIFF,
            raw=payload,
            context=context,
            source_ref=f"{repo}#PR{(payload.get('pull_request') or {}).get('number')}",
        )
        session.commit()
        return {"status": "accepted", "requirement_id": str(row.id)}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
