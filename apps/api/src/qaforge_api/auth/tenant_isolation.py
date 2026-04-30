"""Tenant-isolation alert hooks — Story 3.1.1.

PRD Phase-3 AC: cross-tenant access attempts return 404 (not 403) and
are alerted. The 404 part is enforced by RLS — a SELECT for a row that
exists in tenant B from a session bound to tenant A returns zero rows,
which the service layer surfaces as :class:`ResourceNotFoundError`,
which the router maps to HTTP 404. There is no authorization branch
that could leak existence via a 403.

The "alerted" part is this module: every 404 on a tenant-scoped fetch
is logged as ``tenant_isolation.resource_miss`` so a security team can
grep for cross-tenant probing patterns. The log line carries the
tenant id, the actor, the resource type, and the resource id — never
the resource payload, since by definition we couldn't read it.

The decision to *not* page on every miss is deliberate: a legitimate
404 (e.g. a stale UI link to a deleted workspace) and a malicious
cross-tenant probe look identical at this layer. We log + leave
correlation to downstream tooling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from qaforge_api.auth.context import RequestContext

_log = structlog.get_logger("qaforge_api.auth.tenant_isolation")


def emit_resource_miss(
    *,
    context: RequestContext,
    resource_type: str,
    resource_id: object,
) -> None:
    """Emit a structured alert for a tenant-scoped 404.

    Routers call this from their ``ResourceNotFoundError`` handler so
    the line carries the tenant + actor + resource that was missed.
    Safe to call on every miss — log volume is bounded by request
    rate, and the structured key makes downstream filtering trivial.
    """
    _log.info(
        "tenant_isolation.resource_miss",
        tenant_id=str(context.tenant_id),
        actor_user_id=(str(context.user_id) if context.user_id is not None else None),
        correlation_id=context.correlation_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
    )


__all__ = ["emit_resource_miss"]
