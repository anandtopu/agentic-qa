"""prompt_pins

Story 3.4.1 — workspace-level pin from ``(workspace_id, agent)`` to
the prompt version that production traffic should use. A missing pin
falls back to the registry's ``latest()``; an experiment overrides
the pin while it's active.

Revision ID: 0012_prompt_pins
Revises: 0011_user_roles
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_prompt_pins"
down_revision: str | None = "0011_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_pins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("pinned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            name="fk_prompt_pins_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_prompt_pins_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pinned_by"],
            ["users.id"],
            name="fk_prompt_pins_pinned_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_pins"),
        sa.UniqueConstraint(
            "workspace_id",
            "agent_name",
            name="uq_prompt_pins_workspace_agent",
        ),
    )
    op.create_index(
        "ix_prompt_pins_tenant",
        "prompt_pins",
        ["tenant_id"],
    )

    op.execute("ALTER TABLE prompt_pins ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE prompt_pins FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY prompt_pins_tenant_isolation ON prompt_pins
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS prompt_pins_tenant_isolation ON prompt_pins;"
    )
    op.execute("ALTER TABLE prompt_pins DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_prompt_pins_tenant", table_name="prompt_pins")
    op.drop_table("prompt_pins")
