"""model_registry

Story 6.2.1 — track every Claude / OpenAI / Gemini model release the
platform has been asked to evaluate, the eval scorecard that backs
the decision, and the go/no-go verdict. Powers the Epic 6.2 SLA:
"a new flagship model is evaluated and a decision recorded within
14 days of release".

Revision ID: 0016_model_registry
Revises: 0015_agent_feedback
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_model_registry"
down_revision: str | None = "0015_agent_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=True),
        sa.Column("released_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'candidate'"),
        ),
        sa.Column("eval_scorecard_id", sa.String(length=128), nullable=True),
        sa.Column("eval_scorecard_path", sa.String(length=500), nullable=True),
        sa.Column("decision", sa.String(length=8), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("decision_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deprecation_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('candidate','pinned','deprecated','rejected')",
            name="ck_model_registry_status_enum",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('go','no_go')",
            name="ck_model_registry_decision_enum",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_model_registry_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name="fk_model_registry_decided_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_registry"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "model_id",
            name="uq_model_registry_tenant_provider_model",
        ),
    )
    op.create_index(
        "ix_model_registry_tenant_status",
        "model_registry",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_model_registry_awaiting_decision",
        "model_registry",
        ["tenant_id", sa.text("released_at DESC")],
        postgresql_where=sa.text("decision IS NULL AND status = 'candidate'"),
    )

    op.execute("ALTER TABLE model_registry ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE model_registry FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY model_registry_tenant_isolation ON model_registry
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS model_registry_tenant_isolation ON model_registry;")
    op.execute("ALTER TABLE model_registry DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_model_registry_awaiting_decision", table_name="model_registry")
    op.drop_index("ix_model_registry_tenant_status", table_name="model_registry")
    op.drop_table("model_registry")
