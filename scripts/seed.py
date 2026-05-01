"""Demo workspace seed.

Story 0.3.6 ACs: ``make seed`` runs end-to-end without errors and is
idempotent so re-running cannot corrupt state. Phase 0 has no entities
modelled yet — the first ones arrive with Story 1.1.1 (Workspace CRUD).

Until then, this script:

* Verifies the database is reachable and migrations are at head.
* Logs a clear "nothing to seed yet" message so onboarding doesn't fail.
* Provides the call structure each future entity will plug into.

When Story 1.1.1 lands, replace ``_seed_demo_workspace`` with the real
insert; the orchestration around it (idempotency, error handling, exit
code) stays put.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import structlog
from sqlalchemy import text

from aqao_api.config import get_settings
from aqao_api.db import get_engine
from aqao_api.logging import configure_logging, get_logger

DEMO_WORKSPACE_NAME = "demo-workspace"


def _seed_demo_workspace(log: structlog.stdlib.BoundLogger) -> None:
    """Phase 0 placeholder — no entities exist yet.

    Story 1.1.1 will insert into ``workspaces`` here. Keep idempotent:
    select-then-insert keyed on (tenant_id, name).
    """
    log.info(
        "seed.deferred",
        message="no entities exist yet; first seed lands with Story 1.1.1",
        target=DEMO_WORKSPACE_NAME,
    )


def _verify_database_reachable(log: structlog.stdlib.BoundLogger) -> None:
    engine = get_engine()
    with engine.connect() as conn:
        version = conn.execute(text("select 1")).scalar_one()
    log.info("seed.db_ok", probe_value=version)


def _verify_migrations_at_head(log: structlog.stdlib.BoundLogger) -> None:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("select version_num from alembic_version")).scalar_one_or_none()
    if result is None:
        log.warning(
            "seed.migrations_not_applied",
            hint="run `make migrate` before `make seed`",
        )
        sys.exit(2)
    log.info("seed.migrations_ok", head=result)


def main(steps: list[Callable[[structlog.stdlib.BoundLogger], None]] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("aqao_api.seed")
    log.info("seed.start", env=settings.env)

    pipeline = steps or [
        _verify_database_reachable,
        _verify_migrations_at_head,
        _seed_demo_workspace,
    ]
    for step in pipeline:
        step(log)

    log.info("seed.done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
