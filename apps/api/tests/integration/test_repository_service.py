"""Integration tests for RepositoryService — Story 1.1.2.

Hits Postgres for the partial unique index and RLS verification, plus
the stub GitHub client to verify the link/unlink workflow.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models.workspace import ApplicationType
from aqao_api.integrations.github.stub_client import StubGitHubClient
from aqao_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)
from aqao_api.services.repository import RepositoryService
from aqao_api.services.workspace import WorkspaceCreate, WorkspaceService

pytestmark = pytest.mark.integration


def _ctx(tenant_id: uuid.UUID, user_id: uuid.UUID | None = None) -> RequestContext:
    return RequestContext(tenant_id=tenant_id, user_id=user_id, correlation_id=None)


def _make_workspace(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    ws_svc = WorkspaceService(session)
    workspace = ws_svc.create(
        WorkspaceCreate(name="Payments", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    return workspace.id


@pytest.mark.asyncio
async def test_link_persists_and_audits(db_session: Session, tenant_id: uuid.UUID) -> None:
    workspace_id = _make_workspace(db_session, tenant_id)
    stub = StubGitHubClient()
    stub.register_repository(
        installation_id=42,
        full_name="org/payments",
        default_branch="develop",
        private=True,
    )
    svc = RepositoryService(db_session, stub)

    repo = await svc.link(
        workspace_id=workspace_id,
        installation_id=42,
        full_name="org/payments",
        context=_ctx(tenant_id),
    )

    assert repo.full_name == "org/payments"
    assert repo.default_branch == "develop"
    assert repo.private is True
    assert repo.unlinked_at is None

    audit = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE action = 'repository.link'")
    ).scalar_one()
    assert audit == 1


@pytest.mark.asyncio
async def test_link_denormalises_repo_url_onto_workspace(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    workspace_id = _make_workspace(db_session, tenant_id)
    svc = RepositoryService(db_session, StubGitHubClient())

    await svc.link(
        workspace_id=workspace_id,
        installation_id=1,
        full_name="acme/widgets",
        context=_ctx(tenant_id),
    )
    repo_url = db_session.execute(
        text("SELECT repo_url FROM workspaces WHERE id = :id"),
        {"id": str(workspace_id)},
    ).scalar_one()
    assert repo_url == "https://github.com/acme/widgets"


@pytest.mark.asyncio
async def test_link_when_workspace_missing_raises_not_found(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    svc = RepositoryService(db_session, StubGitHubClient())
    with pytest.raises(ResourceNotFoundError):
        await svc.link(
            workspace_id=uuid.uuid4(),
            installation_id=1,
            full_name="x/y",
            context=_ctx(tenant_id),
        )


@pytest.mark.asyncio
async def test_link_rejects_when_active_link_exists(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    workspace_id = _make_workspace(db_session, tenant_id)
    svc = RepositoryService(db_session, StubGitHubClient())

    await svc.link(
        workspace_id=workspace_id,
        installation_id=1,
        full_name="org/repo-a",
        context=_ctx(tenant_id),
    )
    with pytest.raises(DuplicateResourceError):
        await svc.link(
            workspace_id=workspace_id,
            installation_id=2,
            full_name="org/repo-b",
            context=_ctx(tenant_id),
        )


@pytest.mark.asyncio
async def test_unlink_marks_unlinked_and_calls_revoke(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    workspace_id = _make_workspace(db_session, tenant_id)
    stub = StubGitHubClient()
    svc = RepositoryService(db_session, stub)

    repo = await svc.link(
        workspace_id=workspace_id,
        installation_id=99,
        full_name="org/svc",
        context=_ctx(tenant_id),
    )
    db_session.commit()

    unlinked = await svc.unlink(workspace_id=workspace_id, context=_ctx(tenant_id))
    assert unlinked.id == repo.id
    assert unlinked.unlinked_at is not None
    assert stub.revoked_installations == [99]


@pytest.mark.asyncio
async def test_unlink_succeeds_locally_even_if_revoke_fails(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    workspace_id = _make_workspace(db_session, tenant_id)
    stub = StubGitHubClient(fail_on_revoke=True)
    svc = RepositoryService(db_session, stub)

    await svc.link(
        workspace_id=workspace_id,
        installation_id=1,
        full_name="org/repo",
        context=_ctx(tenant_id),
    )
    unlinked = await svc.unlink(workspace_id=workspace_id, context=_ctx(tenant_id))

    assert unlinked.unlinked_at is not None
    audit_payload = db_session.execute(
        text(
            "SELECT payload FROM audit_events "
            "WHERE action = 'repository.unlink' ORDER BY created_at DESC LIMIT 1"
        )
    ).scalar_one()
    assert audit_payload["revoke_succeeded"] is False


@pytest.mark.asyncio
async def test_relink_after_unlink_is_allowed(db_session: Session, tenant_id: uuid.UUID) -> None:
    """The partial unique index permits historical (unlinked) rows to coexist."""
    workspace_id = _make_workspace(db_session, tenant_id)
    stub = StubGitHubClient()
    svc = RepositoryService(db_session, stub)

    await svc.link(
        workspace_id=workspace_id,
        installation_id=1,
        full_name="org/repo",
        context=_ctx(tenant_id),
    )
    await svc.unlink(workspace_id=workspace_id, context=_ctx(tenant_id))
    relinked = await svc.link(
        workspace_id=workspace_id,
        installation_id=2,
        full_name="org/repo",  # same full_name
        context=_ctx(tenant_id),
    )
    assert relinked.unlinked_at is None
