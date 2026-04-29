"""Database layer: declarative base, session factory, model registry.

Models are imported here so Alembic's ``target_metadata`` sees them when
autogenerating migrations. Adding a new model means importing it from
``qaforge_api.db.models`` and re-exporting via ``__all__`` below.
"""

from __future__ import annotations

from qaforge_api.db.base import Base, metadata
from qaforge_api.db.session import (
    get_engine,
    get_sessionmaker,
    reset_session_factory_cache,
    tenant_scoped_session,
)

__all__ = [
    "Base",
    "get_engine",
    "get_sessionmaker",
    "metadata",
    "reset_session_factory_cache",
    "tenant_scoped_session",
]
