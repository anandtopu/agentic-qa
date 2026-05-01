"""Unit tests for ModelLifecycleService — Story 6.2.1.

The DB-backed integration is covered by the Postgres + RLS suite;
here we exercise the in-process state machine + SLA math using a
stub session that holds ModelRegistryEntry rows in memory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    ModelDecision,
    ModelLifecycleStatus,
    ModelRegistryEntry,
)
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.model_lifecycle import (
    DEFAULT_DECISION_SLA,
    InvalidLifecycleTransitionError,
    ModelLifecycleService,
)

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id=_TENANT,
        user_id=_USER,
        correlation_id="trace-model",
    )


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class _StubSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = 0
        self._by_id: dict[UUID, ModelRegistryEntry] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, ModelRegistryEntry):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            if obj.updated_at is None:
                obj.updated_at = obj.created_at
            self._by_id[obj.id] = obj

    def flush(self) -> None:
        self.flushed += 1

    def get(self, model: type, pk: UUID) -> Any | None:
        if model is ModelRegistryEntry:
            return self._by_id.get(pk)
        return None

    def scalars(self, stmt: Any) -> _ScalarResult:
        rows = list(self._iter_filtered(stmt))
        rows = self._apply_order(rows, stmt)
        return _ScalarResult(rows)

    def _iter_filtered(self, stmt: Any) -> list[ModelRegistryEntry]:
        rows: list[ModelRegistryEntry] = list(self._by_id.values())
        where = getattr(stmt, "whereclause", None)
        if where is None:
            return rows
        return [r for r in rows if _matches(r, where)]

    def _apply_order(
        self, rows: list[ModelRegistryEntry], stmt: Any
    ) -> list[ModelRegistryEntry]:
        order = getattr(stmt, "_order_by_clauses", None) or []
        if not order:
            return rows
        clause = order[0]
        col = getattr(clause, "element", clause)
        col_name = getattr(col, "key", None)
        if col_name is None:
            return rows
        descending = "DESC" in str(clause).upper()
        return sorted(
            rows,
            key=lambda r: getattr(r, col_name),
            reverse=descending,
        )


def _matches(row: ModelRegistryEntry, clause: Any) -> bool:
    children = list(clause.get_children()) if hasattr(clause, "get_children") else []
    op_name = getattr(getattr(clause, "operator", None), "__name__", "")
    if op_name == "and_":
        return all(_matches(row, child) for child in children)
    left = getattr(clause, "left", None)
    right = getattr(clause, "right", None)
    if left is None or right is None:
        return True
    col_name = getattr(left, "key", None)
    if col_name is None:
        return True
    value = getattr(right, "value", None)
    actual = getattr(row, col_name, None)
    if op_name == "eq":
        return actual == value
    if op_name == "is_":
        return actual is value
    if op_name == "isnot":
        return actual is not value
    return True


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def service(session: _StubSession) -> ModelLifecycleService:
    return ModelLifecycleService(session, audit=None)  # type: ignore[arg-type]


def _register(
    service: ModelLifecycleService,
    *,
    provider: str = "anthropic",
    model_id: str = "claude-opus-4-7",
    family: str | None = "opus",
    released_at: datetime | None = None,
) -> ModelRegistryEntry:
    return service.register(
        context=_ctx(),
        provider=provider,
        model_id=model_id,
        family=family,
        released_at=released_at or datetime(2026, 4, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------- register


def test_register_creates_candidate(service: ModelLifecycleService) -> None:
    row = _register(service)
    assert row.status == ModelLifecycleStatus.CANDIDATE.value
    assert row.tenant_id == _TENANT
    assert row.decision is None
    assert row.decision_at is None


def test_register_is_idempotent_on_provider_model_pair(
    service: ModelLifecycleService,
) -> None:
    first = _register(service)
    second = _register(service)
    assert first.id == second.id


def test_register_emits_audit_event_when_audit_present(
    session: _StubSession,
) -> None:
    captured: list[dict[str, Any]] = []

    class _RecordingAudit:
        def record(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    svc = ModelLifecycleService(
        session,  # type: ignore[arg-type]
        audit=_RecordingAudit(),  # type: ignore[arg-type]
    )
    _register(svc)
    assert any(c["action"] == "model_registry.registered" for c in captured)


# ---------------------------------------------------------- decision


def test_record_go_decision_pins_model(service: ModelLifecycleService) -> None:
    row = _register(service)
    out = service.record_decision(
        context=_ctx(),
        entry_id=row.id,
        decision=ModelDecision.GO,
        rationale="passes evals + 12% cost win",
    )
    assert out.status == ModelLifecycleStatus.PINNED.value
    assert out.decision == "go"
    assert out.decision_at is not None
    assert out.decided_by_user_id == _USER


def test_record_no_go_decision_rejects(service: ModelLifecycleService) -> None:
    row = _register(service)
    out = service.record_decision(
        context=_ctx(),
        entry_id=row.id,
        decision=ModelDecision.NO_GO,
        rationale="fails classifier accuracy gate",
    )
    assert out.status == ModelLifecycleStatus.REJECTED.value
    assert out.decision == "no_go"


def test_decision_on_already_decided_entry_raises(
    service: ModelLifecycleService,
) -> None:
    row = _register(service)
    service.record_decision(
        context=_ctx(),
        entry_id=row.id,
        decision=ModelDecision.GO,
        rationale="ok",
    )
    with pytest.raises(InvalidLifecycleTransitionError):
        service.record_decision(
            context=_ctx(),
            entry_id=row.id,
            decision=ModelDecision.NO_GO,
            rationale="changed mind",
        )


def test_decision_unknown_id_raises_not_found(
    service: ModelLifecycleService,
) -> None:
    with pytest.raises(ResourceNotFoundError):
        service.record_decision(
            context=_ctx(),
            entry_id=uuid.uuid4(),
            decision=ModelDecision.GO,
            rationale="ok",
        )


# ---------------------------------------------------------- deprecate


def test_deprecate_pinned_model_succeeds(service: ModelLifecycleService) -> None:
    row = _register(service)
    service.record_decision(
        context=_ctx(),
        entry_id=row.id,
        decision=ModelDecision.GO,
        rationale="ok",
    )
    sunset = datetime(2026, 7, 1, tzinfo=UTC)
    out = service.deprecate(
        context=_ctx(),
        entry_id=row.id,
        deprecation_at=sunset,
    )
    assert out.status == ModelLifecycleStatus.DEPRECATED.value
    assert out.deprecation_at == sunset


def test_deprecate_candidate_is_invalid_transition(
    service: ModelLifecycleService,
) -> None:
    row = _register(service)
    with pytest.raises(InvalidLifecycleTransitionError):
        service.deprecate(
            context=_ctx(),
            entry_id=row.id,
            deprecation_at=datetime(2026, 7, 1, tzinfo=UTC),
        )


# ---------------------------------------------------------- attach scorecard


def test_attach_scorecard_records_link(service: ModelLifecycleService) -> None:
    row = _register(service)
    out = service.attach_scorecard(
        context=_ctx(),
        entry_id=row.id,
        eval_scorecard_id="scorecard-2026-04-15-claude-opus-4-7",
        eval_scorecard_path="packages/eval/scorecards/2026-04-15.json",
    )
    assert out.eval_scorecard_id == "scorecard-2026-04-15-claude-opus-4-7"
    assert out.eval_scorecard_path == "packages/eval/scorecards/2026-04-15.json"


# ---------------------------------------------------------- awaiting-decision SLA


def test_awaiting_decision_returns_only_undecided_candidates(
    service: ModelLifecycleService,
) -> None:
    a = _register(
        service,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    b = _register(
        service,
        provider="openai",
        model_id="gpt-9",
        released_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    # Decide a → it should drop out of the awaiting list.
    service.record_decision(
        context=_ctx(),
        entry_id=a.id,
        decision=ModelDecision.GO,
        rationale="ok",
    )

    rows = service.awaiting_decision(
        tenant_id=_TENANT,
        now=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert len(rows) == 1
    assert rows[0].entry.id == b.id


def test_awaiting_decision_marks_breach_past_14_days(
    service: ModelLifecycleService,
) -> None:
    old = _register(
        service,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    new = _register(
        service,
        provider="openai",
        model_id="gpt-9",
        released_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    rows = service.awaiting_decision(
        tenant_id=_TENANT,
        now=datetime(2026, 4, 30, tzinfo=UTC),
    )
    by_id = {r.entry.id: r for r in rows}
    assert by_id[old.id].sla_breached is True
    assert by_id[old.id].age_days == 29
    assert by_id[new.id].sla_breached is False
    assert by_id[new.id].age_days == 2


def test_awaiting_decision_orders_oldest_first(
    service: ModelLifecycleService,
) -> None:
    newer = _register(
        service,
        provider="openai",
        model_id="gpt-9",
        released_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    older = _register(
        service,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    rows = service.awaiting_decision(
        tenant_id=_TENANT,
        now=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert [r.entry.id for r in rows] == [older.id, newer.id]


def test_awaiting_decision_default_sla_is_14_days(
    service: ModelLifecycleService,
) -> None:
    assert timedelta(days=14) == DEFAULT_DECISION_SLA


# ---------------------------------------------------------- list


def test_list_filters_by_status(service: ModelLifecycleService) -> None:
    a = _register(service, model_id="claude-opus-4-7")
    b = _register(service, model_id="claude-haiku-4-5")
    service.record_decision(
        context=_ctx(),
        entry_id=a.id,
        decision=ModelDecision.GO,
        rationale="ok",
    )
    pinned = service.list_entries(tenant_id=_TENANT, status=ModelLifecycleStatus.PINNED)
    assert len(pinned) == 1 and pinned[0].id == a.id
    candidates = service.list_entries(tenant_id=_TENANT, status=ModelLifecycleStatus.CANDIDATE)
    assert len(candidates) == 1 and candidates[0].id == b.id
