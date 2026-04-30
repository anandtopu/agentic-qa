"""external_issues

Story 3.2.x — links from QAForge defect classifications to issues
created in external trackers (Jira, GitHub Issues). Used for:

* dedup: "we already opened a Jira for this signal_id within 24h —
  don't open another";
* close-sync: a webhook from the external tracker can mark the
  matching defect record as resolved without polling.

The link is **per signal_id + provider + project** so the same defect
can have one Jira issue and one GitHub issue without colliding.

Revision ID: 0014_external_issues
Revises: 0013_flakiness
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_external_issues"
down_revision: str | None = "0013_flakiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signal_id", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("project_key", sa.String(length=100), nullable=False),
        sa.Column("issue_key", sa.String(length=200), nullable=False),
        sa.Column("issue_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("opened_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "opened_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "closed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_synced_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_external_issues_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_external_issues_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["classification_id"],
            ["failure_classifications.id"],
            name="fk_external_issues_classification_id_failure_classifications",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by"],
            ["users.id"],
            name="fk_external_issues_opened_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_external_issues"),
        sa.CheckConstraint(
            "provider IN ('jira','github')",
            name="ck_external_issues_provider",
        ),
        sa.CheckConstraint(
            "status IN ('open','in_progress','resolved','closed','rejected')",
            name="ck_external_issues_status",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            "issue_key",
            name="uq_external_issues_workspace_provider_issue",
        ),
    )
    op.create_index(
        "ix_external_issues_workspace_signal_provider_opened",
        "external_issues",
        ["workspace_id", "signal_id", "provider", sa.text("opened_at DESC")],
    )
    op.create_index(
        "ix_external_issues_tenant_status",
        "external_issues",
        ["tenant_id", "status"],
    )

    op.execute("ALTER TABLE external_issues ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE external_issues FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY external_issues_tenant_isolation ON external_issues
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS external_issues_tenant_isolation ON external_issues;"
    )
    op.execute("ALTER TABLE external_issues DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_external_issues_tenant_status", table_name="external_issues")
    op.drop_index(
        "ix_external_issues_workspace_signal_provider_opened",
        table_name="external_issues",
    )
    op.drop_table("external_issues")
