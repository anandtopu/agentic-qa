"""workspace_environments and workspace_policies

Story 1.1.3 — per-environment configs and versioned agent policies.

* ``workspace_environments`` — one row per environment (dev/staging/prod);
  unique within a workspace.
* ``workspace_policies`` — append-only versioned policy log; exactly one
  row per workspace may have ``active=true`` (partial unique index).

Revision ID: 0004_envs_policies
Revises: 0003_repositories
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_envs_policies"
down_revision: str | None = "0003_repositories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = ("workspace_environments", "workspace_policies")


def upgrade() -> None:
    op.create_table(
        "workspace_environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_production",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_workspace_environments_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_environments_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_environments"),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_workspace_environments_workspace_name"
        ),
    )
    op.create_index(
        "ix_workspace_environments_tenant_id_workspace_id",
        "workspace_environments",
        ["tenant_id", "workspace_id"],
    )

    op.create_table(
        "workspace_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_yaml", sa.Text(), nullable=False),
        sa.Column(
            "parsed",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_workspace_policies_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_policies_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_workspace_policies_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_policies"),
        sa.UniqueConstraint(
            "workspace_id", "version", name="uq_workspace_policies_workspace_version"
        ),
    )
    op.create_index(
        "ix_workspace_policies_tenant_id_workspace_id_created_at",
        "workspace_policies",
        ["tenant_id", "workspace_id", sa.text("created_at DESC")],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_workspace_policies_one_active
        ON workspace_policies (workspace_id)
        WHERE active = true;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_workspace_environments_set_updated_at
        BEFORE UPDATE ON workspace_environments
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id::text = current_setting('app.current_tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
            """
        )


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workspace_environments_set_updated_at "
        "ON workspace_environments;"
    )
    op.execute("DROP INDEX IF EXISTS uq_workspace_policies_one_active;")
    op.drop_index(
        "ix_workspace_policies_tenant_id_workspace_id_created_at",
        table_name="workspace_policies",
    )
    op.drop_table("workspace_policies")
    op.drop_index(
        "ix_workspace_environments_tenant_id_workspace_id",
        table_name="workspace_environments",
    )
    op.drop_table("workspace_environments")
