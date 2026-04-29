"""Alembic migration environment.

Reads the database URL from ``QAFORGE_DATABASE_URL`` via the application
settings (ADR-0008: secrets never live in alembic.ini). Imports the ORM
model registry so autogeneration sees every mapped entity.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from qaforge_api.config import get_settings
from qaforge_api.db import metadata
from qaforge_api.db import models as _models  # noqa: F401  (registers ORM classes)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _resolve_database_url() -> str:
    """Resolve the URL from settings; allow CLI override via ``-x url=...``."""
    cli_args = context.get_x_argument(as_dictionary=True)
    return cli_args.get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=_resolve_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section["sqlalchemy.url"] = _resolve_database_url()

    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
