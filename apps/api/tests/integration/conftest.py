"""Fixtures for DB-backed integration tests.

Requires ``make dev`` to be running (or at least Postgres reachable at
``AQAO_DATABASE_URL``). Tests are marked ``integration`` so unit-only
runs (``make test-unit``) skip them.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from aqao_api.db import (
    get_engine,
    get_sessionmaker,
    reset_session_factory_cache,
)

ALEMBIC_INI = pytest.importorskip("pathlib").Path(__file__).resolve().parents[3] / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrations_at_head() -> Iterator[None]:
    """Bring the test DB to head once per session."""
    if not os.getenv("AQAO_DATABASE_URL"):
        pytest.skip("AQAO_DATABASE_URL not set; skipping integration suite")
    reset_session_factory_cache()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _truncate_between_tests() -> Iterator[None]:
    """Clean tables before each test to keep them independent.

    TRUNCATE bypasses RLS — this fixture intentionally uses a raw engine
    connection (no ``app.current_tenant_id``) so tests start from empty.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE TABLE audit_events, workspaces, users, tenants RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    """Insert a tenant directly (bypassing RLS) and return its id."""
    engine = get_engine()
    new_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": str(new_id), "name": "Test Tenant", "slug": f"t-{new_id.hex[:8]}"},
        )
    return new_id


@pytest.fixture()
def other_tenant_id() -> uuid.UUID:
    engine = get_engine()
    new_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": str(new_id), "name": "Other Tenant", "slug": f"o-{new_id.hex[:8]}"},
        )
    return new_id


@pytest.fixture()
def session_factory() -> Iterator[None]:
    """Reset the cached sessionmaker (lru_cache) between tests."""
    yield
    reset_session_factory_cache()


@pytest.fixture()
def db_session(tenant_id: uuid.UUID) -> Iterator:
    """A session with ``app.current_tenant_id`` already set.

    Mirrors what :func:`tenant_scoped_session` does for HTTP requests.
    """
    factory = get_sessionmaker()
    session = factory()
    try:
        session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant_id)},
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
