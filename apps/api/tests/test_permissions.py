"""Tests for the workspace RBAC permission matrix — Story 3.1.2.

PRD Phase-3 AC: permission matrix has 100% coverage in policy tests.
We assert:

* Every :class:`Permission` member has an entry in
  :data:`PERMISSION_MATRIX`.
* Every :class:`Role` has at least one permission (no orphan roles).
* The five expected role/permission semantics from the PRD hold:
  - viewer never gains write access
  - approver never gains workspace-edit power
  - engineer cannot decide approvals
  - destructive admin actions are owner-only
  - admin is a strict superset of engineer for non-destructive actions
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from aqao_api.auth import (
    PERMISSION_MATRIX,
    Permission,
    RequestContext,
    Role,
    require_permission,
    role_has,
)


def _ctx(role: Role | None) -> RequestContext:
    return RequestContext(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        correlation_id=None,
        role=role,
    )


# ---------------------------------------------------------------- coverage


def test_every_permission_has_a_matrix_entry() -> None:
    missing = [p for p in Permission if p not in PERMISSION_MATRIX]
    assert not missing, f"Permission(s) missing from matrix: {missing}"


def test_every_matrix_entry_lists_at_least_one_role() -> None:
    empty = [p for p, roles in PERMISSION_MATRIX.items() if not roles]
    assert not empty, f"Permission(s) with empty role set: {empty}"


def test_every_role_has_at_least_one_permission() -> None:
    granted: set[Role] = set()
    for roles in PERMISSION_MATRIX.values():
        granted.update(roles)
    orphans = [r for r in Role if r not in granted]
    assert not orphans, f"Role(s) with no permissions: {orphans}"


# ---------------------------------------------------------------- semantics


def test_viewer_never_gains_write_access() -> None:
    write_perms = {
        Permission.WORKSPACE_EDIT,
        Permission.WORKSPACE_DELETE,
        Permission.POLICY_EDIT,
        Permission.TEST_PLAN_EDIT,
        Permission.TEST_RUN_START,
        Permission.APPROVAL_DECIDE,
        Permission.USER_INVITE,
        Permission.USER_REMOVE,
        Permission.USER_ROLE_CHANGE,
        Permission.EVAL_RUN,
        Permission.EVAL_BASELINE_PROMOTE,
    }
    leaks = [p for p in write_perms if role_has(Role.VIEWER, p)]
    assert not leaks, f"Viewer leaks write access on: {leaks}"


def test_approver_cannot_edit_workspace_or_policy() -> None:
    forbidden = {
        Permission.WORKSPACE_EDIT,
        Permission.WORKSPACE_DELETE,
        Permission.POLICY_EDIT,
        Permission.USER_INVITE,
        Permission.USER_REMOVE,
        Permission.USER_ROLE_CHANGE,
    }
    leaks = [p for p in forbidden if role_has(Role.APPROVER, p)]
    assert not leaks, f"Approver leaked privileged actions: {leaks}"


def test_engineer_cannot_decide_approvals() -> None:
    """PRD §9.10 — approval decisions belong to approver/admin/owner.
    The engineer role is the run-the-day-to-day role and must not be
    able to self-approve a destructive operation."""
    assert not role_has(Role.ENGINEER, Permission.APPROVAL_DECIDE)


def test_destructive_admin_actions_are_owner_only() -> None:
    """workspace:delete + user:role_change are deliberately owner-only."""
    assert PERMISSION_MATRIX[Permission.WORKSPACE_DELETE] == frozenset({Role.OWNER})
    assert PERMISSION_MATRIX[Permission.USER_ROLE_CHANGE] == frozenset({Role.OWNER})


def test_admin_strictly_supersets_engineer_for_non_destructive_actions() -> None:
    """Anything an engineer can do, an admin can also do."""
    engineer_perms = {p for p in Permission if role_has(Role.ENGINEER, p)}
    for p in engineer_perms:
        assert role_has(Role.ADMIN, p), (
            f"engineer has {p} but admin does not — admin must superset engineer"
        )


# ---------------------------------------------------------------- enforcement


def test_require_permission_raises_403_when_role_missing() -> None:
    enforcer = require_permission(Permission.APPROVAL_DECIDE)
    with pytest.raises(HTTPException) as exc:
        enforcer(_ctx(role=None))
    assert exc.value.status_code == 403


def test_require_permission_raises_403_when_role_not_allowed() -> None:
    enforcer = require_permission(Permission.APPROVAL_DECIDE)
    with pytest.raises(HTTPException) as exc:
        enforcer(_ctx(role=Role.VIEWER))
    assert exc.value.status_code == 403
    assert "approval:decide" in exc.value.detail


def test_require_permission_passes_through_when_role_allowed() -> None:
    enforcer = require_permission(Permission.APPROVAL_DECIDE)
    ctx = enforcer(_ctx(role=Role.APPROVER))
    assert ctx.role is Role.APPROVER


def test_role_header_unknown_value_is_rejected_by_context_parser() -> None:
    """X-AQAO-Role with an unknown value should not silently
    downgrade to viewer — that would mask a misconfigured client."""
    from aqao_api.auth.context import _parse_role

    with pytest.raises(HTTPException) as exc:
        _parse_role("super_admin")
    assert exc.value.status_code == 400


def test_role_header_absent_resolves_to_none() -> None:
    """No header == no role; downstream require_permission then 403s."""
    from aqao_api.auth.context import _parse_role

    assert _parse_role(None) is None
