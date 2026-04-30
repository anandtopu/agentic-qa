"""repositories

Story 1.1.2 — GitHub repository linkage. Adds a tenant-scoped
``repositories`` table with RLS, an updated_at trigger, and a partial
unique index that prevents two active links to the same ``full_name``
within a workspace while allowing historical (unlinked) rows to remain.

Revision ID: 0003_repositories
Revises: 0002_workspaces
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_repositories"
down_revision: str | None = "0002_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=True),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("full_name", sa.String(length=400), nullable=False),
        sa.Column(
            "default_branch",
            sa.String(length=100),
            nullable=False,
            server_default="main",
        ),
        sa.Column(
            "private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("html_url", sa.String(length=500), nullable=True),
        sa.Column("linked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "linked_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unlinked_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            name="fk_repositories_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_repositories_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["linked_by"],
            ["users.id"],
            name="fk_repositories_linked_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
    )
    op.create_index(
        "ix_repositories_tenant_id_workspace_id",
        "repositories",
        ["tenant_id", "workspace_id"],
    )
    # Partial unique: only one active linkage per (workspace, full_name).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_repositories_workspace_full_name_active
        ON repositories (workspace_id, full_name)
        WHERE unlinked_at IS NULL;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_repositories_set_updated_at
        BEFORE UPDATE ON repositories
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    op.execute("ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE repositories FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY repositories_tenant_isolation ON repositories
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS repositories_tenant_isolation ON repositories;")
    op.execute("ALTER TABLE repositories DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS trg_repositories_set_updated_at ON repositories;")
    op.execute("DROP INDEX IF EXISTS uq_repositories_workspace_full_name_active;")
    op.drop_index("ix_repositories_tenant_id_workspace_id", table_name="repositories")
    op.drop_table("repositories")
