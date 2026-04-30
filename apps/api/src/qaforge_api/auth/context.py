"""RequestContext + FastAPI dependencies.

Resolves the calling tenant and user for the lifetime of one request.
Phase 1 reads them from headers; Phase 3 will swap the header source
for verified OIDC claims without touching call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from qaforge_api.auth.roles import Role

TENANT_HEADER = "X-QAForge-Tenant-Id"
USER_HEADER = "X-QAForge-User-Id"
ROLE_HEADER = "X-QAForge-Role"
CORRELATION_HEADER = "X-QAForge-Trace-Id"


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Identity + correlation context resolved from the inbound request."""

    tenant_id: UUID
    user_id: UUID | None
    correlation_id: str | None
    role: Role | None = None


def _parse_uuid(raw: str | None, *, header_name: str) -> UUID | None:
    if raw is None:
        return None
    try:
        return UUID(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{header_name} is not a valid UUID",
        ) from exc


def _parse_role(raw: str | None) -> Role | None:
    """Parse the X-QAForge-Role header into a Role enum value, or None
    if absent. Unknown roles raise 400 — silent downgrade to ``viewer``
    would mask a misconfigured client."""
    if raw is None:
        return None
    try:
        return Role(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{ROLE_HEADER} is not a valid role: {raw!r}",
        ) from exc


async def get_request_context(
    x_qaforge_tenant_id: str | None = Header(default=None, alias=TENANT_HEADER),
    x_qaforge_user_id: str | None = Header(default=None, alias=USER_HEADER),
    x_qaforge_role: str | None = Header(default=None, alias=ROLE_HEADER),
    x_qaforge_trace_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> RequestContext | None:
    """Resolve a context from headers, or return ``None`` if no tenant claim."""
    tenant_id = _parse_uuid(x_qaforge_tenant_id, header_name=TENANT_HEADER)
    if tenant_id is None:
        return None
    user_id = _parse_uuid(x_qaforge_user_id, header_name=USER_HEADER)
    role = _parse_role(x_qaforge_role)
    return RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=x_qaforge_trace_id,
        role=role,
    )


async def require_request_context(
    context: RequestContext | None = None,
    x_qaforge_tenant_id: str | None = Header(default=None, alias=TENANT_HEADER),
    x_qaforge_user_id: str | None = Header(default=None, alias=USER_HEADER),
    x_qaforge_role: str | None = Header(default=None, alias=ROLE_HEADER),
    x_qaforge_trace_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> RequestContext:
    """Variant that 401s when the tenant claim is missing."""
    resolved = context or await get_request_context(
        x_qaforge_tenant_id=x_qaforge_tenant_id,
        x_qaforge_user_id=x_qaforge_user_id,
        x_qaforge_role=x_qaforge_role,
        x_qaforge_trace_id=x_qaforge_trace_id,
    )
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing tenant identity",
        )
    return resolved
