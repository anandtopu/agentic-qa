"""Migration scaffold tests.

Two layers:

* **Unit** — load the Alembic config, confirm the script directory is
  discoverable, the head revision matches the baseline, and the ORM
  metadata is empty (Phase 0 expectation; Phase 1 will add the first
  entity and this test will be tightened).
* **Integration** — actually run ``upgrade head`` and ``downgrade base``
  against a live Postgres. Skipped unless the integration marker is
  selected (``make test-int``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from aqao_api.db import metadata

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    return cfg


def test_alembic_ini_is_discoverable() -> None:
    assert ALEMBIC_INI.is_file(), f"missing {ALEMBIC_INI}"


def test_script_directory_loads_and_has_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())
    assert revisions, "no migrations found"
    head = script.get_current_head()
    assert head is not None


def test_metadata_contains_phase_1_core_entities() -> None:
    # Story 1.1.1 added the first entities. Tighten this further when
    # Phase 2 / Phase 3 introduce more.
    expected = {"tenants", "users", "workspaces", "audit_events"}
    assert expected.issubset(set(metadata.tables))


@pytest.mark.integration
def test_upgrade_head_then_downgrade_base() -> None:
    """Full round-trip against the docker-compose Postgres."""
    from alembic import command

    if not os.getenv("AQAO_DATABASE_URL"):
        pytest.skip("AQAO_DATABASE_URL not set; skipping migration integration test")

    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
