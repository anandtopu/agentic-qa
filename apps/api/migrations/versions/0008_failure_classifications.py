"""failure_classifications

Story 1.7 — failure triage records produced by the heuristic + LLM
classifier. One row per classified failure signal.

Revision ID: 0008_failure_class
Revises: 0007_test_runs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_failure_class"
down_revision: str | None = "0007_test_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "failure_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signal_id", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "confidence",
            sa.Numeric(3, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column("classified_by", sa.String(length=16), nullable=False),
        sa.Column("rule", sa.String(length=100), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column(
            "raw_signal",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_failure_classifications_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            name="fk_failure_classifications_test_run_id_test_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_task_id"],
            ["agent_tasks.id"],
            name="fk_failure_classifications_agent_task_id_agent_tasks",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_failure_classifications"),
        sa.CheckConstraint(
            "category IN ('product_defect','test_issue','environment_issue',"
            "'flaky_test','data_issue','unknown')",
            name="ck_failure_classifications_category",
        ),
        sa.CheckConstraint(
            "classified_by IN ('heuristic','llm')",
            name="ck_failure_classifications_classified_by",
        ),
        sa.CheckConstraint(
            "confidence >= 0.00 AND confidence <= 1.00",
            name="ck_failure_classifications_confidence_range",
        ),
    )
    op.create_index(
        "ix_failure_classifications_run_category",
        "failure_classifications",
        ["test_run_id", "category"],
    )
    op.create_index(
        "ix_failure_classifications_tenant_classified_by_created_at",
        "failure_classifications",
        ["tenant_id", "classified_by", sa.text("created_at DESC")],
    )

    op.execute("ALTER TABLE failure_classifications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE failure_classifications FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY failure_classifications_tenant_isolation
        ON failure_classifications
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS failure_classifications_tenant_isolation "
        "ON failure_classifications;"
    )
    op.execute("ALTER TABLE failure_classifications DISABLE ROW LEVEL SECURITY;")
    op.drop_index(
        "ix_failure_classifications_tenant_classified_by_created_at",
        table_name="failure_classifications",
    )
    op.drop_index(
        "ix_failure_classifications_run_category",
        table_name="failure_classifications",
    )
    op.drop_table("failure_classifications")
