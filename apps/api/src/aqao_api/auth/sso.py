"""SSO Verifier Protocol + group-to-role mapping — Story 3.1.3.

The Phase-3 plan calls for OIDC + SAML, with group-to-role mapping
that resolves a verified token / assertion into a workspace
:class:`Role`. We ship the seam now and a stub :class:`StaticVerifier`
that's good enough for tests + local dev; the OIDC/SAML adapters
land separately once a real IdP is provisioned (the per-cuts
agreement made in the Phase-3 plan review).

Public surface:

* :class:`SsoIdentity` — verified principal (issuer + subject + email
  + group claims).
* :class:`SsoVerifier` Protocol — anything that can take a credential
  string and produce an ``SsoIdentity`` or raise ``SsoError``.
* :class:`StaticVerifier` — in-memory stub used by tests.
* :class:`GroupRoleMapper` — pure function from ``set[str]`` of group
  names to a :class:`Role`, with a tenant-scoped fallback.
* :func:`resolve_request_context` — stitches the verifier + mapper
  into a :class:`RequestContext` so future routers can declare the
  dependency once the API switches off the header shim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from aqao_api.auth.context import RequestContext
from aqao_api.auth.permissions import Role


class SsoError(RuntimeError):
    """Credential could not be verified — issuer rejected, signature
    bad, token expired, etc. Routers map this to HTTP 401."""


@dataclass(slots=True, frozen=True)
class SsoIdentity:
    """A verified principal returned by an :class:`SsoVerifier`.

    Carries enough information for the group-to-role mapper to pick a
    :class:`Role` and for the Control Plane to resolve a tenant + user
    record. Tenant resolution is intentionally external: the verifier
    knows who the user is at the IdP; the API knows which workspace
    that maps to.
    """

    issuer: str
    subject: str  # opaque IdP user id
    email: str
    name: str | None = None
    groups: frozenset[str] = field(default_factory=frozenset)
    correlation_id: str | None = None


class SsoVerifier(Protocol):
    """Verifies a credential and returns the identity, or raises."""

    def verify(self, credential: str) -> SsoIdentity: ...


@dataclass(slots=True)
class StaticVerifier:
    """Test/dev-only verifier — looks credentials up in a fixed map."""

    identities: Mapping[str, SsoIdentity]

    def verify(self, credential: str) -> SsoIdentity:
        if credential not in self.identities:
            raise SsoError(f"unknown credential: {credential!r}")
        return self.identities[credential]


@dataclass(slots=True)
class GroupRoleMapper:
    """Resolve a set of IdP group names into a workspace :class:`Role`.

    Configuration is a list of (group_name, role) pairs evaluated in
    order — the **first match wins**, so put the most-privileged
    mapping first if a user might be in multiple groups. ``default``
    is returned if no group matches; ``None`` means "no role" and
    leaves :class:`RequestContext.role` as ``None`` (which then 403s
    on any gated endpoint via :func:`require_permission`).
    """

    mapping: tuple[tuple[str, Role], ...]
    default: Role | None = None

    def resolve(self, groups: frozenset[str]) -> Role | None:
        for group_name, role in self.mapping:
            if group_name in groups:
                return role
        return self.default


def resolve_request_context(
    *,
    credential: str,
    verifier: SsoVerifier,
    mapper: GroupRoleMapper,
    tenant_id: UUID,
    user_id: UUID | None,
) -> RequestContext:
    """Combine verifier + mapper into a :class:`RequestContext`.

    The header-based context dependency stays as the Phase-1 shim;
    routers that opt into SSO can call this helper from a custom
    dependency once the OIDC/SAML adapters land. The signature
    matches what an SSO middleware would produce — ``tenant_id`` +
    ``user_id`` come from the workspace's IdP-to-tenant mapping
    (PRD §11.1), not from the IdP itself.
    """
    identity = verifier.verify(credential)
    role = mapper.resolve(identity.groups)
    return RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=identity.correlation_id,
        role=role,
    )


__all__ = [
    "GroupRoleMapper",
    "SsoError",
    "SsoIdentity",
    "SsoVerifier",
    "StaticVerifier",
    "resolve_request_context",
]
