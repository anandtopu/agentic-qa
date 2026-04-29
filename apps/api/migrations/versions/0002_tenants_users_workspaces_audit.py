"""tenants, users, workspaces, audit_events

Story 1.1.1 — foundational entities for Workspace CRUD with row-level
multi-tenancy (ADR-0007). Adds:

* ``tenants`` (no RLS — must be readable for tenant resolution)
* ``users``, ``workspaces``, ``audit_events`` (RLS-enabled,
  tenant-scoped)
* ``set_updated_at`` trigger function applied to mutable tables
* RLS policies tied to ``app.current_tenant_id`` session variable

Revision ID: 0002_workspaces
Revises: 0001_baseline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_workspaces"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = ("users", "workspaces", "audit_events")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;
        """
    )

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            name="fk_users_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
    op.create_index(
        "ix_users_tenant_id_created_at",
        "users",
        ["tenant_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("repo_url", sa.String(length=500), nullable=True),
        sa.Column(
            "default_branch",
            sa.String(length=100),
            nullable=False,
            server_default="main",
        ),
        sa.Column(
            "application_type", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "environments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_workspaces_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_workspaces_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_workspaces_tenant_id_name"),
        sa.CheckConstraint(
            "application_type IN "
            "('web_api','web_ui','web_full_stack','mobile_app',"
            "'backend_service','library','other')",
            name="ck_workspaces_application_type",
        ),
    )
    op.create_index(
        "ix_workspaces_tenant_id_created_at",
        "workspaces",
        ["tenant_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=200), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("signature", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_audit_events_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_tenant_id_created_at",
        "audit_events",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_events_tenant_id_resource_type_resource_id",
        "audit_events",
        ["tenant_id", "resource_type", "resource_id"],
    )

    # updated_at triggers on mutable tables.
    for table in ("tenants", "users", "workspaces"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )

    # RLS — per ADR-0007.
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

    # audit_events is append-only at the application role level — Phase 2
    # Story 2.4.1 adds DB role split that also forbids UPDATE/DELETE.


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    for table in ("tenants", "users", "workspaces"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table};")

    op.drop_index(
        "ix_audit_events_tenant_id_resource_type_resource_id",
        table_name="audit_events",
    )
    op.drop_index("ix_audit_events_tenant_id_created_at", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_workspaces_tenant_id_created_at", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index("ix_users_tenant_id_created_at", table_name="users")
    op.drop_table("users")

    op.drop_table("tenants")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
