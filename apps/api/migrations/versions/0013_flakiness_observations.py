"""flakiness_observations

Story 3.3.1 — append-only ledger of (test_id, passed) outcomes used to
compute rolling pass-rates over 14/30/90-day windows. RLS-isolated by
tenant.

The table is intentionally narrow: ``test_id`` is the durable
identifier the test framework emits (suite + test name + parametrise
id), ``passed`` is the verdict, ``observed_at`` is when. Heavyweight
test_run linkage stays optional so a backfill from CI logs can land
rows without a corresponding test_run record.

Revision ID: 0013_flakiness
Revises: 0012_prompt_pins
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_flakiness"
down_revision: str | None = "0012_prompt_pins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flakiness_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_id", sa.String(length=500), nullable=False),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "observed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_flakiness_observations_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_flakiness_observations_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            name="fk_flakiness_observations_test_run_id_test_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_flakiness_observations"),
    )
    op.create_index(
        "ix_flakiness_observations_workspace_test_observed",
        "flakiness_observations",
        ["workspace_id", "test_id", sa.text("observed_at DESC")],
    )
    op.create_index(
        "ix_flakiness_observations_tenant_observed",
        "flakiness_observations",
        ["tenant_id", sa.text("observed_at DESC")],
    )

    op.execute("ALTER TABLE flakiness_observations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE flakiness_observations FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY flakiness_observations_tenant_isolation ON flakiness_observations
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS flakiness_observations_tenant_isolation "
        "ON flakiness_observations;"
    )
    op.execute("ALTER TABLE flakiness_observations DISABLE ROW LEVEL SECURITY;")
    op.drop_index(
        "ix_flakiness_observations_tenant_observed",
        table_name="flakiness_observations",
    )
    op.drop_index(
        "ix_flakiness_observations_workspace_test_observed",
        table_name="flakiness_observations",
    )
    op.drop_table("flakiness_observations")
