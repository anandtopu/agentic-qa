"""Auth context and dependencies.

Phase 1 ships a header-based auth shim — the API layer asks the request
for ``X-QAForge-Tenant-Id`` and ``X-QAForge-User-Id`` headers and binds
them as a :class:`RequestContext`. Phase 3 (Story 3.1.3) replaces the
header source with OIDC/SAML claims behind the same dependency, so call
sites don't move when real auth lands.
"""

from qaforge_api.auth.context import (
    RequestContext,
    get_request_context,
    require_request_context,
)
from qaforge_api.auth.permissions import (
    PERMISSION_MATRIX,
    Permission,
    Role,
    require_permission,
    role_has,
)
from qaforge_api.auth.tenant_isolation import emit_resource_miss

__all__ = [
    "PERMISSION_MATRIX",
    "Permission",
    "RequestContext",
    "Role",
    "emit_resource_miss",
    "get_request_context",
    "require_permission",
    "require_request_context",
    "role_has",
]
