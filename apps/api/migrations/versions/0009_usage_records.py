"""usage_records

Story 2.5.1+2 — durable cost ledger. Append-only, RLS-enabled. Mirror
of :class:`aqao_agents.llm.types.UsageRecord` with workspace +
test_run + agent_name added so cost dashboards can slice by any of
those.

Revision ID: 0009_usage
Revises: 0008_failure_class
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_usage"
down_revision: str | None = "0008_failure_class"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cached_prompt_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "usd_cost",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_usage_records_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_usage_records_workspace_id_workspaces",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            name="fk_usage_records_test_run_id_test_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_records"),
    )
    op.create_index(
        "ix_usage_records_tenant_created_at",
        "usage_records",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_usage_records_workspace_agent_created_at",
        "usage_records",
        ["workspace_id", "agent_name", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_usage_records_test_run",
        "usage_records",
        ["test_run_id"],
        postgresql_where=sa.text("test_run_id IS NOT NULL"),
    )

    op.execute("ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE usage_records FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY usage_records_tenant_isolation ON usage_records
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS usage_records_tenant_isolation ON usage_records;"
    )
    op.execute("ALTER TABLE usage_records DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_usage_records_test_run", table_name="usage_records")
    op.drop_index(
        "ix_usage_records_workspace_agent_created_at", table_name="usage_records"
    )
    op.drop_index("ix_usage_records_tenant_created_at", table_name="usage_records")
    op.drop_table("usage_records")
