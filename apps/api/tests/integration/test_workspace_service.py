"""Integration tests for WorkspaceService.

Hit a real Postgres so RLS, JSONB, and the unique constraint behave the
way they will in production.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models.workspace import ApplicationType
from qaforge_api.services.errors import DuplicateResourceError, ResourceNotFoundError
from qaforge_api.services.workspace import (
    WorkspaceCreate,
    WorkspaceService,
    WorkspaceUpdate,
)

pytestmark = pytest.mark.integration


def _ctx(tenant_id: uuid.UUID, user_id: uuid.UUID | None = None) -> RequestContext:
    return RequestContext(tenant_id=tenant_id, user_id=user_id, correlation_id=None)


def test_create_persists_and_audits(db_session: Session, tenant_id: uuid.UUID) -> None:
    svc = WorkspaceService(db_session)
    workspace = svc.create(
        WorkspaceCreate(name="Payments", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )

    assert workspace.id is not None
    assert workspace.tenant_id == tenant_id

    audit_count = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE action = 'workspace.create'")
    ).scalar_one()
    assert audit_count == 1


def test_create_rejects_duplicate_name_within_tenant(
    db_session: Session, tenant_id: uuid.UUID
) -> None:
    svc = WorkspaceService(db_session)
    svc.create(
        WorkspaceCreate(name="Payments", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    with pytest.raises(DuplicateResourceError):
        svc.create(
            WorkspaceCreate(name="Payments", application_type=ApplicationType.WEB_API),
            context=_ctx(tenant_id),
        )


def test_get_returns_workspace(db_session: Session, tenant_id: uuid.UUID) -> None:
    svc = WorkspaceService(db_session)
    created = svc.create(
        WorkspaceCreate(name="Payments", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    fetched = svc.get(created.id)
    assert fetched.id == created.id


def test_get_unknown_id_raises_not_found(db_session: Session, tenant_id: uuid.UUID) -> None:
    svc = WorkspaceService(db_session)
    with pytest.raises(ResourceNotFoundError):
        svc.get(uuid.uuid4())


def test_list_excludes_archived_by_default(db_session: Session, tenant_id: uuid.UUID) -> None:
    svc = WorkspaceService(db_session)
    a = svc.create(
        WorkspaceCreate(name="A", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    svc.create(
        WorkspaceCreate(name="B", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    svc.archive(a.id, context=_ctx(tenant_id))
    db_session.commit()

    visible = svc.list()
    assert {w.name for w in visible} == {"B"}

    all_workspaces = svc.list(include_archived=True)
    assert {w.name for w in all_workspaces} == {"A", "B"}


def test_update_records_audit_with_changes(db_session: Session, tenant_id: uuid.UUID) -> None:
    svc = WorkspaceService(db_session)
    created = svc.create(
        WorkspaceCreate(name="Old", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    svc.update(
        created.id,
        WorkspaceUpdate(name="New", description="now described"),
        context=_ctx(tenant_id),
    )
    refreshed = svc.get(created.id)
    assert refreshed.name == "New"
    assert refreshed.description == "now described"

    audit = db_session.execute(
        text(
            "SELECT payload FROM audit_events WHERE action = 'workspace.update' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).scalar_one()
    assert "name" in audit["changes"]
    assert audit["changes"]["name"] == {"old": "Old", "new": "New"}


def test_rls_blocks_cross_tenant_read(
    db_session: Session, tenant_id: uuid.UUID, other_tenant_id: uuid.UUID
) -> None:
    """A workspace created under one tenant must not be visible from another."""
    svc = WorkspaceService(db_session)
    created = svc.create(
        WorkspaceCreate(name="A", application_type=ApplicationType.WEB_API),
        context=_ctx(tenant_id),
    )
    db_session.commit()

    # Same connection but switch tenant context. RLS filters out the row.
    db_session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(other_tenant_id)},
    )
    with pytest.raises(ResourceNotFoundError):
        svc.get(created.id)
