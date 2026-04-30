"""user roles

Story 3.1.2 — adds a ``role`` column to ``users`` for the workspace
RBAC matrix (owner | admin | engineer | approver | viewer). Existing
rows default to ``viewer`` so the migration is safe to run on a
populated table; operators promote known users via a seed script.

Revision ID: 0011_user_roles
Revises: 0010_approvals
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_user_roles"
down_revision: str | None = "0010_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_VALUES = ("owner", "admin", "engineer", "approver", "viewer")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="viewer",
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('owner','admin','engineer','approver','viewer')",
    )
    op.create_index(
        "ix_users_tenant_role",
        "users",
        ["tenant_id", "role"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_tenant_role", table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")


__all__ = ["_ROLE_VALUES"]
