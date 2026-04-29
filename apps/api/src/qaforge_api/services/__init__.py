"""Domain services.

The router layer is thin — translation between HTTP and Python — and
delegates state changes to services here. Services accept a Session and
a RequestContext, never the FastAPI Request object, so they are usable
from background workers and scripts as well as from API handlers.
"""

from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ServiceError,
)
from qaforge_api.services.workspace import WorkspaceService

__all__ = [
    "AuditService",
    "DuplicateResourceError",
    "ResourceNotFoundError",
    "ServiceError",
    "WorkspaceService",
]
