"""Unit tests for PromptPinService — Story 3.4.1.

The DB-backed query path runs under integration; here we validate the
pin lifecycle (create, update, delete, missing-pin → None) and the
audit fan-out using a stub session, matching the pattern used for
ApprovalService.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import AuditEvent, PromptPin
from qaforge_api.services.errors import ResourceNotFoundError
from qaforge_api.services.prompt_pin import PromptPinService


class _StubSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self._store: dict[tuple[type, UUID], Any] = {}
        self.flushed = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._store[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)

    def get(self, cls: type, ident: UUID) -> Any | None:
        return self._store.get((cls, ident))

    def delete(self, obj: Any) -> None:
        self._store.pop((type(obj), obj.id), None)

    # Stand-in for the SQLAlchemy 2.x scalars(stmt) call. Pin lookups
    # in PromptPinService go through select() — we intercept the
    # filters that the service builds and match against the in-memory
    # store on workspace_id + agent_name.
    def scalars(self, stmt: Any) -> Any:
        # Inspect the SQLAlchemy Select for its WHERE clauses and
        # reduce to a list of matching PromptPin rows. Tests that
        # don't go through this path can ignore the stub.
        from sqlalchemy.sql import operators

        candidates = [row for (cls, _), row in self._store.items() if cls is PromptPin]
        for crit in stmt.whereclause.get_children() if stmt.whereclause is not None else []:
            if not hasattr(crit, "left") or not hasattr(crit, "right"):
                continue
            col = getattr(crit.left, "key", None)
            value = getattr(crit.right, "value", None)
            if col is None or value is None:
                continue
            if crit.operator is operators.eq:
                candidates = [r for r in candidates if getattr(r, col) == value]
        return _ScalarResult(candidates)


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def context() -> RequestContext:
    return RequestContext(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        correlation_id="trace-1",
    )


@pytest.fixture
def service(session: _StubSession) -> PromptPinService:
    return PromptPinService(session)  # type: ignore[arg-type]


def _audit_actions(session: _StubSession) -> list[str]:
    return [a.action for a in session.added if isinstance(a, AuditEvent)]


def test_get_pinned_version_returns_none_when_no_pin(
    service: PromptPinService,
) -> None:
    assert service.get_pinned_version(workspace_id=uuid.uuid4(), agent_name="planner") is None


def test_set_pin_creates_new_pin_and_audits(
    service: PromptPinService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    workspace_id = uuid.uuid4()
    pin = service.set_pin(
        workspace_id=workspace_id,
        agent_name="planner",
        version="1.2.0",
        context=context,
        note="pin to validated version",
    )
    assert pin.version == "1.2.0"
    assert pin.workspace_id == workspace_id
    assert pin.pinned_by == context.user_id
    assert "prompt_pin.set" in _audit_actions(session)


def test_set_pin_updates_existing_pin(
    service: PromptPinService,
    context: RequestContext,
) -> None:
    workspace_id = uuid.uuid4()
    service.set_pin(
        workspace_id=workspace_id,
        agent_name="planner",
        version="1.0.0",
        context=context,
    )
    service.set_pin(
        workspace_id=workspace_id,
        agent_name="planner",
        version="2.0.0",
        context=context,
    )
    assert service.get_pinned_version(workspace_id=workspace_id, agent_name="planner") == "2.0.0"


def test_set_pin_promote_action_distinguishes_experiment_winner(
    service: PromptPinService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    """Story 3.4.2 promotes a winning variant by calling ``set_pin``
    with ``action='prompt_pin.promote'`` so the audit log can
    distinguish a manual pin from an experiment outcome."""
    service.set_pin(
        workspace_id=uuid.uuid4(),
        agent_name="planner",
        version="2.0.0",
        context=context,
        action="prompt_pin.promote",
    )
    assert "prompt_pin.promote" in _audit_actions(session)


def test_delete_pin_removes_row_and_audits(
    service: PromptPinService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    workspace_id = uuid.uuid4()
    service.set_pin(
        workspace_id=workspace_id,
        agent_name="planner",
        version="1.0.0",
        context=context,
    )
    service.delete_pin(workspace_id=workspace_id, agent_name="planner", context=context)
    assert "prompt_pin.delete" in _audit_actions(session)
    assert service.get_pinned_version(workspace_id=workspace_id, agent_name="planner") is None


def test_delete_pin_raises_when_missing(
    service: PromptPinService,
    context: RequestContext,
) -> None:
    with pytest.raises(ResourceNotFoundError):
        service.delete_pin(
            workspace_id=uuid.uuid4(),
            agent_name="planner",
            context=context,
        )
