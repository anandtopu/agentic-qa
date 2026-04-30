"""Unit tests for AgentFeedbackService — Story 6.3.1.

The DB-backed integration is covered by the Postgres + RLS suite;
here we exercise the in-process logic (record + query filtering +
weekly-review rollup + eval-case conversion idempotency) using a
stub session that holds AgentFeedback rows in memory.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import AgentFeedback, FeedbackRating
from qaforge_api.services.agent_feedback import (
    AgentFeedbackService,
    FeedbackNotConvertibleError,
)

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_WORKSPACE = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id=_TENANT,
        user_id=_USER,
        correlation_id="trace-feedback",
    )


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class _StubSession:
    """In-memory session covering the surface AgentFeedbackService uses."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = 0
        self._by_id: dict[UUID, AgentFeedback] = {}

    # ----- ORM surface -----

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, AgentFeedback):
            if obj.id is None:
                obj.id = uuid.uuid4()
            self._by_id[obj.id] = obj

    def flush(self) -> None:
        self.flushed += 1

    def get(self, model: type, pk: UUID) -> Any | None:
        if model is AgentFeedback:
            return self._by_id.get(pk)
        return None

    # ----- query path -----

    def scalars(self, stmt: Any) -> _ScalarResult:
        rows = list(self._iter_filtered(stmt))
        rows = self._apply_order(rows, stmt)
        rows = self._apply_limit(rows, stmt)
        return _ScalarResult(rows)

    def scalar(self, stmt: Any) -> Any:
        rows = list(self._iter_filtered(stmt))
        rows = self._apply_limit(rows, stmt)
        # we only emit `select(func.count())` against AgentFeedback
        return len(rows)

    def _iter_filtered(self, stmt: Any) -> list[AgentFeedback]:
        rows: list[AgentFeedback] = list(self._by_id.values())
        where = getattr(stmt, "whereclause", None)
        if where is None:
            return rows
        return [r for r in rows if _matches(r, where)]

    def _apply_order(
        self, rows: list[AgentFeedback], stmt: Any
    ) -> list[AgentFeedback]:
        order = getattr(stmt, "_order_by_clauses", None) or []
        if not order:
            return rows
        # Single-column order is sufficient for the queries we issue.
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

    def _apply_limit(
        self, rows: list[AgentFeedback], stmt: Any
    ) -> list[AgentFeedback]:
        limit = getattr(stmt, "_limit", None)
        if limit is None:
            return rows
        try:
            n = int(limit)
        except (TypeError, ValueError):
            return rows
        return rows[:n]


def _matches(row: AgentFeedback, clause: Any) -> bool:
    """Walk a SQLAlchemy where-clause tree, supporting AND of leaf comparisons."""
    children = list(clause.get_children()) if hasattr(clause, "get_children") else []
    op_name = getattr(getattr(clause, "operator", None), "__name__", "")
    if op_name == "and_":
        return all(_matches(row, child) for child in children)
    # Leaf comparison
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
    if op_name == "ge":
        return actual >= value
    if op_name == "is_":
        return actual is value
    if op_name == "isnot":
        return actual is not value
    return True


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def service(session: _StubSession, tmp_path: Path) -> AgentFeedbackService:
    return AgentFeedbackService(
        session,  # type: ignore[arg-type]
        audit=None,
        eval_dataset_dir=tmp_path,
        snapshot_provider=lambda fb: {
            "agent_kind": fb.agent_kind,
            "resource_id": str(fb.resource_id),
            "comment": fb.comment,
        },
    )


def _record(
    service: AgentFeedbackService,
    *,
    rating: FeedbackRating = FeedbackRating.DOWN,
    agent_kind: str = "classifier",
    resource_type: str = "failure_classification",
    comment: str | None = None,
    workspace_id: UUID = _WORKSPACE,
) -> AgentFeedback:
    return service.record(
        context=_ctx(),
        workspace_id=workspace_id,
        agent_kind=agent_kind,
        resource_type=resource_type,
        resource_id=uuid.uuid4(),
        rating=rating,
        comment=comment,
    )


# ---------------------------------------------------------------- record


def test_record_persists_and_flushes(
    service: AgentFeedbackService, session: _StubSession
) -> None:
    row = _record(service, rating=FeedbackRating.UP, comment="nice plan")
    assert row.id is not None
    assert row.tenant_id == _TENANT
    assert row.workspace_id == _WORKSPACE
    assert row.rating == "up"
    assert row.comment == "nice plan"
    assert session.flushed >= 1
    assert any(isinstance(r, AgentFeedback) for r in session.added)


def test_record_audits_when_audit_service_supplied(
    session: _StubSession, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []

    class _RecordingAudit:
        def record(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    svc = AgentFeedbackService(
        session,  # type: ignore[arg-type]
        audit=_RecordingAudit(),  # type: ignore[arg-type]
        eval_dataset_dir=tmp_path,
    )
    _record(svc, rating=FeedbackRating.DOWN)
    assert len(captured) == 1
    event = captured[0]
    assert event["action"] == "agent_feedback.recorded"
    assert event["resource_type"] == "agent_feedback"
    assert event["payload"]["rating"] == "down"


# ---------------------------------------------------------------- query


def test_query_filters_by_agent_and_rating(service: AgentFeedbackService) -> None:
    _record(service, agent_kind="classifier", rating=FeedbackRating.DOWN)
    _record(service, agent_kind="classifier", rating=FeedbackRating.UP)
    _record(service, agent_kind="planner", rating=FeedbackRating.DOWN)

    got = service.query(
        workspace_id=_WORKSPACE,
        agent_kind="classifier",
        rating=FeedbackRating.DOWN,
    )
    assert len(got) == 1
    assert got[0].agent_kind == "classifier"
    assert got[0].rating == "down"


def test_query_isolates_by_workspace(service: AgentFeedbackService) -> None:
    other = uuid.uuid4()
    _record(service, rating=FeedbackRating.DOWN, workspace_id=other)
    _record(service, rating=FeedbackRating.UP, workspace_id=_WORKSPACE)

    got = service.query(workspace_id=_WORKSPACE)
    assert len(got) == 1
    assert got[0].workspace_id == _WORKSPACE


# ---------------------------------------------------------------- weekly review


def test_weekly_review_rolls_up_counts_per_agent(
    service: AgentFeedbackService,
) -> None:
    _record(service, agent_kind="classifier", rating=FeedbackRating.DOWN)
    _record(service, agent_kind="classifier", rating=FeedbackRating.DOWN)
    _record(service, agent_kind="classifier", rating=FeedbackRating.UP)
    _record(service, agent_kind="planner", rating=FeedbackRating.DOWN)

    review = service.weekly_review(workspace_id=_WORKSPACE)
    assert review.overall_total == 4
    assert review.overall_down_count == 3
    assert review.overall_converted == 0
    assert {s.agent_kind for s in review.by_agent} == {"classifier", "planner"}
    classifier = next(s for s in review.by_agent if s.agent_kind == "classifier")
    assert classifier.total_feedback == 3
    assert classifier.down_count == 2
    assert classifier.up_count == 1
    assert classifier.down_rate == pytest.approx(2 / 3)
    assert classifier.pending_conversion == 2
    assert classifier.converted == 0
    assert classifier.conversion_rate == 0.0


def test_weekly_review_excludes_rows_outside_window(
    service: AgentFeedbackService,
) -> None:
    old = _record(service, rating=FeedbackRating.DOWN)
    # Move the row's submitted_at into the past, beyond the 7-day window.
    old.submitted_at = datetime.now(UTC) - timedelta(days=14)
    _record(service, rating=FeedbackRating.UP)

    review = service.weekly_review(
        workspace_id=_WORKSPACE,
        window=timedelta(days=7),
    )
    assert review.overall_total == 1
    assert review.overall_down_count == 0


def test_weekly_review_pending_items_are_unconverted_downs(
    service: AgentFeedbackService,
) -> None:
    a = _record(service, rating=FeedbackRating.DOWN)
    _record(service, rating=FeedbackRating.UP)
    b = _record(service, rating=FeedbackRating.DOWN)
    # Mark `a` as converted so only `b` is pending.
    a.converted_at = datetime.now(UTC)

    review = service.weekly_review(workspace_id=_WORKSPACE)
    pending_ids = {row.id for row in review.pending_items}
    assert pending_ids == {b.id}


# ---------------------------------------------------------------- conversion


def test_convert_to_eval_appends_jsonl_and_stamps_row(
    service: AgentFeedbackService, tmp_path: Path
) -> None:
    row = _record(
        service,
        agent_kind="classifier",
        rating=FeedbackRating.DOWN,
        comment="false positive",
    )
    outcome = service.convert_to_eval_case(context=_ctx(), feedback_id=row.id)

    assert outcome.append_result.created is True
    target = tmp_path / "classifier" / "feedback_cases.jsonl"
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert payload["id"] == f"feedback-{row.id}"
    assert payload["metadata"]["agent_kind"] == "classifier"
    assert "feedback" in payload["labels"]
    assert "regression" in payload["labels"]

    refreshed = service.get(row.id)
    assert refreshed.eval_case_id == outcome.append_result.case_id
    assert refreshed.eval_case_path == "classifier/feedback_cases.jsonl"
    assert refreshed.converted_at is not None


def test_convert_to_eval_is_idempotent(
    service: AgentFeedbackService, tmp_path: Path
) -> None:
    row = _record(service, rating=FeedbackRating.DOWN)
    first = service.convert_to_eval_case(context=_ctx(), feedback_id=row.id)
    second = service.convert_to_eval_case(context=_ctx(), feedback_id=row.id)
    assert first.append_result.created is True
    assert second.append_result.created is False
    target = tmp_path / row.agent_kind / "feedback_cases.jsonl"
    lines = [
        line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 1


def test_convert_to_eval_rejects_thumbs_up(service: AgentFeedbackService) -> None:
    row = _record(service, rating=FeedbackRating.UP)
    with pytest.raises(FeedbackNotConvertibleError):
        service.convert_to_eval_case(context=_ctx(), feedback_id=row.id)


def test_convert_to_eval_unknown_id_raises_not_found(
    service: AgentFeedbackService,
) -> None:
    from qaforge_api.services.errors import ResourceNotFoundError

    with pytest.raises(ResourceNotFoundError):
        service.convert_to_eval_case(context=_ctx(), feedback_id=uuid.uuid4())


def test_convert_to_eval_applies_redactor(
    session: _StubSession, tmp_path: Path
) -> None:
    def _redact(text: str) -> str:
        return text.replace("secret-token-xyz", "[REDACTED]")

    svc = AgentFeedbackService(
        session,  # type: ignore[arg-type]
        eval_dataset_dir=tmp_path,
        snapshot_provider=lambda fb: {
            "comment": fb.comment,
            "leak": "secret-token-xyz",
        },
        redact=_redact,
    )
    row = _record(
        svc,
        rating=FeedbackRating.DOWN,
        comment="leaked: secret-token-xyz",
    )
    svc.convert_to_eval_case(context=_ctx(), feedback_id=row.id)
    target = tmp_path / row.agent_kind / "feedback_cases.jsonl"
    payload = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert "secret-token-xyz" not in target.read_text(encoding="utf-8")
    assert payload["inputs"]["leak"] == "[REDACTED]"
    assert payload["metadata"]["comment"] == "leaked: [REDACTED]"
