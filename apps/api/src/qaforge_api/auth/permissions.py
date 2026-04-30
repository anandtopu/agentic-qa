"""Roles + permission matrix — Story 3.1.2.

The platform exposes five workspace roles (PRD §11.1 / Phase-3 plan):

* ``owner`` — full control, including destructive admin actions.
* ``admin`` — manages workspace config + users; can do everything an
  engineer can.
* ``engineer`` — runs tests, edits plans, drives the day-to-day flow.
* ``approver`` — decides on approval gates (PRD §9.10) but does not
  edit workspace config.
* ``viewer`` — read-only audit / dashboard access.

The :class:`Permission` enum names every gated action; the
:data:`PERMISSION_MATRIX` maps each permission to the set of roles
that may exercise it. Routers consume :func:`require_permission` as
a FastAPI dependency.

Test contract (AC: 100% coverage in policy tests): every
:class:`Permission` member must appear in the matrix and every
:class:`Role` must have at least one permission. The matrix is
deliberately explicit — no role is implicitly "above" another.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status

from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.auth.roles import Role

if TYPE_CHECKING:
    from collections.abc import Callable


class Permission(StrEnum):
    # Workspace + tenant config
    WORKSPACE_VIEW = "workspace:view"
    WORKSPACE_EDIT = "workspace:edit"
    WORKSPACE_DELETE = "workspace:delete"
    POLICY_VIEW = "policy:view"
    POLICY_EDIT = "policy:edit"
    USER_INVITE = "user:invite"
    USER_REMOVE = "user:remove"
    USER_ROLE_CHANGE = "user:role_change"

    # Test plans / runs
    TEST_PLAN_VIEW = "test_plan:view"
    TEST_PLAN_EDIT = "test_plan:edit"
    TEST_RUN_START = "test_run:start"
    TEST_RUN_VIEW = "test_run:view"

    # Approvals (PRD §9.10)
    APPROVAL_VIEW = "approval:view"
    APPROVAL_DECIDE = "approval:decide"

    # Auditability + cost
    AUDIT_VIEW = "audit:view"
    USAGE_VIEW = "usage:view"

    # Eval harness
    EVAL_RUN = "eval:run"
    EVAL_BASELINE_PROMOTE = "eval:baseline_promote"


PERMISSION_MATRIX: dict[Permission, frozenset[Role]] = {
    # --- view-everything baseline -----------------------------------
    Permission.WORKSPACE_VIEW: frozenset(
        {Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.APPROVER, Role.VIEWER}
    ),
    Permission.POLICY_VIEW: frozenset(
        {Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.APPROVER, Role.VIEWER}
    ),
    Permission.TEST_PLAN_VIEW: frozenset(
        {Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.APPROVER, Role.VIEWER}
    ),
    Permission.TEST_RUN_VIEW: frozenset(
        {Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.APPROVER, Role.VIEWER}
    ),
    Permission.APPROVAL_VIEW: frozenset(
        {Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.APPROVER, Role.VIEWER}
    ),
    Permission.AUDIT_VIEW: frozenset({Role.OWNER, Role.ADMIN, Role.APPROVER, Role.VIEWER}),
    Permission.USAGE_VIEW: frozenset({Role.OWNER, Role.ADMIN, Role.ENGINEER, Role.VIEWER}),
    # --- engineer day-to-day ----------------------------------------
    Permission.TEST_PLAN_EDIT: frozenset({Role.OWNER, Role.ADMIN, Role.ENGINEER}),
    Permission.TEST_RUN_START: frozenset({Role.OWNER, Role.ADMIN, Role.ENGINEER}),
    Permission.EVAL_RUN: frozenset({Role.OWNER, Role.ADMIN, Role.ENGINEER}),
    # --- approval gates: dedicated approver role ---------------------
    Permission.APPROVAL_DECIDE: frozenset({Role.OWNER, Role.ADMIN, Role.APPROVER}),
    # --- workspace + user admin -------------------------------------
    Permission.WORKSPACE_EDIT: frozenset({Role.OWNER, Role.ADMIN}),
    Permission.POLICY_EDIT: frozenset({Role.OWNER, Role.ADMIN}),
    Permission.USER_INVITE: frozenset({Role.OWNER, Role.ADMIN}),
    Permission.EVAL_BASELINE_PROMOTE: frozenset({Role.OWNER, Role.ADMIN}),
    # --- destructive admin: owner only ------------------------------
    Permission.WORKSPACE_DELETE: frozenset({Role.OWNER}),
    Permission.USER_REMOVE: frozenset({Role.OWNER, Role.ADMIN}),
    Permission.USER_ROLE_CHANGE: frozenset({Role.OWNER}),
}


def role_has(role: Role, permission: Permission) -> bool:
    return role in PERMISSION_MATRIX[permission]


def require_permission(
    permission: Permission,
) -> Callable[[RequestContext], RequestContext]:
    """FastAPI dependency factory — gate an endpoint behind a permission.

    Usage::

        @router.post("/policy")
        def set_policy(
            ...,
            ctx: RequestContext = Depends(require_permission(Permission.POLICY_EDIT)),
        ): ...

    The caller's ``RequestContext`` carries the resolved role (set by
    the auth-context dependency); this helper checks the matrix and
    raises HTTP 403 if the role isn't permitted. A missing role is
    treated as ``viewer`` so unauthenticated calls never gain power.
    """

    def _enforce(
        ctx: RequestContext = Depends(require_request_context),
    ) -> RequestContext:
        if ctx.role is None or not role_has(ctx.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role lacks permission: {permission.value}",
            )
        return ctx

    return _enforce


__all__ = [
    "PERMISSION_MATRIX",
    "Permission",
    "Role",
    "require_permission",
    "role_has",
]
