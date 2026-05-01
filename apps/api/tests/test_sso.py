"""Tests for the SSO Verifier seam — Story 3.1.3.

Real OIDC/SAML provider integration is deferred until credentials are
available; here we validate the Protocol contract, the group→role
mapper, and the dependency-style ``resolve_request_context`` helper.
"""

from __future__ import annotations

import uuid

import pytest

from aqao_api.auth import Role
from aqao_api.auth.sso import (
    GroupRoleMapper,
    SsoError,
    SsoIdentity,
    StaticVerifier,
    resolve_request_context,
)


def _identity(**overrides: object) -> SsoIdentity:
    base: dict[str, object] = {
        "issuer": "https://accounts.example.com",
        "subject": "user-42",
        "email": "alice@example.com",
        "name": "Alice",
        "groups": frozenset({"aqao-engineers"}),
        "correlation_id": "trace-1",
    }
    base.update(overrides)
    return SsoIdentity(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- verifier


def test_static_verifier_returns_identity_for_known_credential() -> None:
    identity = _identity()
    verifier = StaticVerifier(identities={"token-1": identity})
    assert verifier.verify("token-1") is identity


def test_static_verifier_raises_on_unknown_credential() -> None:
    verifier = StaticVerifier(identities={})
    with pytest.raises(SsoError):
        verifier.verify("token-9000")


# ---------------------------------------------------------------- mapper


def test_mapper_first_match_wins() -> None:
    mapper = GroupRoleMapper(
        mapping=(
            ("aqao-owners", Role.OWNER),
            ("aqao-admins", Role.ADMIN),
            ("aqao-engineers", Role.ENGINEER),
        ),
        default=Role.VIEWER,
    )
    role = mapper.resolve(frozenset({"aqao-admins", "aqao-engineers"}))
    # OWNER not present -> ADMIN wins because it's earlier than ENGINEER.
    assert role is Role.ADMIN


def test_mapper_falls_back_to_default_when_no_groups_match() -> None:
    mapper = GroupRoleMapper(
        mapping=(("aqao-owners", Role.OWNER),),
        default=Role.VIEWER,
    )
    assert mapper.resolve(frozenset({"unrelated-group"})) is Role.VIEWER


def test_mapper_returns_none_when_no_default_and_no_match() -> None:
    mapper = GroupRoleMapper(mapping=(("x", Role.OWNER),), default=None)
    assert mapper.resolve(frozenset()) is None


# ---------------------------------------------------------------- glue


def test_resolve_request_context_combines_verifier_and_mapper() -> None:
    identity = _identity(groups=frozenset({"aqao-approvers"}))
    verifier = StaticVerifier(identities={"tok": identity})
    mapper = GroupRoleMapper(
        mapping=(
            ("aqao-owners", Role.OWNER),
            ("aqao-approvers", Role.APPROVER),
            ("aqao-engineers", Role.ENGINEER),
        ),
        default=Role.VIEWER,
    )
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ctx = resolve_request_context(
        credential="tok",
        verifier=verifier,
        mapper=mapper,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    assert ctx.tenant_id == tenant_id
    assert ctx.user_id == user_id
    assert ctx.role is Role.APPROVER
    assert ctx.correlation_id == "trace-1"


def test_resolve_request_context_propagates_verifier_error() -> None:
    verifier = StaticVerifier(identities={})
    mapper = GroupRoleMapper(mapping=(), default=Role.VIEWER)
    with pytest.raises(SsoError):
        resolve_request_context(
            credential="bad",
            verifier=verifier,
            mapper=mapper,
            tenant_id=uuid.uuid4(),
            user_id=None,
        )


def test_unmapped_user_gets_no_role_so_gated_endpoints_403() -> None:
    """A verified-but-unmapped user must NOT default to a real role —
    the failure mode is 'no permissions', not 'viewer everywhere'."""
    identity = _identity(groups=frozenset({"some-other-org-group"}))
    verifier = StaticVerifier(identities={"tok": identity})
    mapper = GroupRoleMapper(mapping=(("aqao-owners", Role.OWNER),))  # no default
    ctx = resolve_request_context(
        credential="tok",
        verifier=verifier,
        mapper=mapper,
        tenant_id=uuid.uuid4(),
        user_id=None,
    )
    assert ctx.role is None
