"""Engine and session factories.

The engine is built lazily so tests can override ``QAFORGE_DATABASE_URL``
before the first call. Two session-creation paths:

* :func:`get_sessionmaker` — raw ``sessionmaker`` for migrations, scripts,
  and tests that don't need RLS.
* :func:`tenant_scoped_session` (FastAPI dependency) — opens a transaction
  and sets ``app.current_tenant_id`` from the request context so RLS
  policies (ADR-0007) apply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def reset_session_factory_cache() -> None:
    """Test helper — call after pointing settings at a fresh DB URL."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


async def tenant_scoped_session(
    context: RequestContext = Depends(require_request_context),
) -> AsyncIterator[Session]:
    """Yield a Session with ``app.current_tenant_id`` set to the caller's tenant.

    Commits on success, rolls back on exception. Use this anywhere the
    Control Plane needs to read or write tenant-scoped tables — direct
    use of :func:`get_sessionmaker` from a request handler skips RLS and
    should be considered a defect.
    """
    factory = get_sessionmaker()
    session = factory()
    try:
        session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(context.tenant_id)},
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
