"""agent_feedback

Story 6.3.1 — append-only ledger of thumbs up/down feedback on
individual agent outputs (test plans, classifications, reports,
risk scores, generated suites). Powers the weekly low-rated review
and the conversion path that turns negatively-rated outputs into
regression cases under ``packages/eval/datasets/<agent>/``.

The reference is intentionally polymorphic — ``(resource_type,
resource_id)`` — so any agent output across the four planes can be
rated without per-resource FK gymnastics.

Revision ID: 0015_agent_feedback
Revises: 0014_external_issues
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_agent_feedback"
down_revision: str | None = "0014_external_issues"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_kind", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "submitted_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("eval_case_id", sa.String(length=128), nullable=True),
        sa.Column("eval_case_path", sa.String(length=500), nullable=True),
        sa.Column(
            "converted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "rating IN ('up','down')",
            name="ck_agent_feedback_rating_enum",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_agent_feedback_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_agent_feedback_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name="fk_agent_feedback_submitted_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_feedback"),
    )
    op.create_index(
        "ix_agent_feedback_workspace_submitted",
        "agent_feedback",
        ["workspace_id", sa.text("submitted_at DESC")],
    )
    op.create_index(
        "ix_agent_feedback_workspace_agent_rating",
        "agent_feedback",
        ["workspace_id", "agent_kind", "rating"],
    )
    op.create_index(
        "ix_agent_feedback_resource",
        "agent_feedback",
        ["resource_type", "resource_id"],
    )
    op.create_index(
        "ix_agent_feedback_pending_conversion",
        "agent_feedback",
        ["workspace_id", "rating", sa.text("submitted_at DESC")],
        postgresql_where=sa.text("converted_at IS NULL AND rating = 'down'"),
    )

    op.execute("ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE agent_feedback FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY agent_feedback_tenant_isolation ON agent_feedback
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_feedback_tenant_isolation ON agent_feedback;")
    op.execute("ALTER TABLE agent_feedback DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_agent_feedback_pending_conversion", table_name="agent_feedback")
    op.drop_index("ix_agent_feedback_resource", table_name="agent_feedback")
    op.drop_index("ix_agent_feedback_workspace_agent_rating", table_name="agent_feedback")
    op.drop_index("ix_agent_feedback_workspace_submitted", table_name="agent_feedback")
    op.drop_table("agent_feedback")
