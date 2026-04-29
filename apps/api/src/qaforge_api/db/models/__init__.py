"""ORM model registry.

Every model module must be imported here so Alembic autogeneration can
see it via ``Base.metadata``. Order does not matter; SQLAlchemy resolves
foreign-key references at metadata-create time.
"""

from __future__ import annotations

from qaforge_api.db.models.audit_event import AuditEvent
from qaforge_api.db.models.tenant import Tenant
from qaforge_api.db.models.user import User
from qaforge_api.db.models.workspace import ApplicationType, Workspace

__all__ = ["ApplicationType", "AuditEvent", "Tenant", "User", "Workspace"]
