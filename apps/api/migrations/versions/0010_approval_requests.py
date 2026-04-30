"""approval_requests

Story 2.1.1 — human approval gates table per PRD §9.10. Holds the
durable record of every approval ask (destructive SQL, prod-env tests,
external issue creation, release readiness, CI changes, high-cost eval
runs) with its lifecycle state. RLS-isolated by tenant.

Revision ID: 0010_approvals
Revises: 0009_usage
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_approvals"
down_revision: str | None = "0009_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "decided_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
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
            name="fk_approval_requests_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_approval_requests_workspace_id_workspaces",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            name="fk_approval_requests_test_run_id_test_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_approval_requests_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name="fk_approval_requests_decided_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_requests"),
        sa.CheckConstraint(
            "state IN ('pending','approved','rejected','expired','cancelled')",
            name="ck_approval_requests_state",
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'destructive_sql',"
            "'production_test_execution',"
            "'external_ticket_creation',"
            "'release_readiness',"
            "'ci_pipeline_modification',"
            "'high_cost_eval_run'"
            ")",
            name="ck_approval_requests_event_type",
        ),
    )
    op.create_index(
        "ix_approval_requests_tenant_state_created_at",
        "approval_requests",
        ["tenant_id", "state", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_approval_requests_workspace_state",
        "approval_requests",
        ["workspace_id", "state"],
        postgresql_where=sa.text("workspace_id IS NOT NULL"),
    )
    op.create_index(
        "ix_approval_requests_test_run",
        "approval_requests",
        ["test_run_id"],
        postgresql_where=sa.text("test_run_id IS NOT NULL"),
    )
    op.create_index(
        "ix_approval_requests_pending_expires",
        "approval_requests",
        ["expires_at"],
        postgresql_where=sa.text("state = 'pending' AND expires_at IS NOT NULL"),
    )

    op.execute("ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE approval_requests FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY approval_requests_tenant_isolation ON approval_requests
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS approval_requests_tenant_isolation ON approval_requests;"
    )
    op.execute("ALTER TABLE approval_requests DISABLE ROW LEVEL SECURITY;")
    op.drop_index(
        "ix_approval_requests_pending_expires", table_name="approval_requests"
    )
    op.drop_index("ix_approval_requests_test_run", table_name="approval_requests")
    op.drop_index(
        "ix_approval_requests_workspace_state", table_name="approval_requests"
    )
    op.drop_index(
        "ix_approval_requests_tenant_state_created_at", table_name="approval_requests"
    )
    op.drop_table("approval_requests")
