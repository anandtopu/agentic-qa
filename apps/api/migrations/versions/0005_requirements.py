"""requirements

Story 1.2 — input artifacts that drive downstream agents. Every type
(``pr_diff``, ``user_story``, ``openapi``, ``postman``, ``sql_schema``)
flows through this table; the per-type parser shapes ``parsed``.

Revision ID: 0005_requirements
Revises: 0004_envs_policies
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_requirements"
down_revision: str | None = "0004_envs_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=500), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "parsed",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("ingested_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            name="fk_requirements_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_requirements_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingested_by"],
            ["users.id"],
            name="fk_requirements_ingested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirements"),
        sa.CheckConstraint(
            "type IN ('pr_diff','user_story','openapi','postman','sql_schema')",
            name="ck_requirements_type",
        ),
        sa.CheckConstraint(
            "status IN ('parsed','failed')",
            name="ck_requirements_status",
        ),
    )
    op.create_index(
        "ix_requirements_tenant_id_workspace_id_created_at",
        "requirements",
        ["tenant_id", "workspace_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_requirements_workspace_id_type",
        "requirements",
        ["workspace_id", "type"],
    )
    op.create_index(
        "ix_requirements_commit_sha",
        "requirements",
        ["commit_sha"],
        postgresql_where=sa.text("commit_sha IS NOT NULL"),
    )

    op.execute(
        """
        CREATE TRIGGER trg_requirements_set_updated_at
        BEFORE UPDATE ON requirements
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute("ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE requirements FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY requirements_tenant_isolation ON requirements
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS requirements_tenant_isolation ON requirements;")
    op.execute("ALTER TABLE requirements DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS trg_requirements_set_updated_at ON requirements;")
    op.drop_index("ix_requirements_commit_sha", table_name="requirements")
    op.drop_index("ix_requirements_workspace_id_type", table_name="requirements")
    op.drop_index(
        "ix_requirements_tenant_id_workspace_id_created_at",
        table_name="requirements",
    )
    op.drop_table("requirements")
