"""Unit tests for EvidenceStoreSnapshotProvider — TD-006.

These exercise the in-process routing + per-resource shaping with an
in-memory fake session (the DB-backed path is integration territory).
The contract: the provider pulls the agent's *real* inputs off the
owning store, and degrades to the resource pointer for unknown types
or pruned rows so eval-case conversion never fails.
"""

from __future__ import annotations

import uuid
from typing import Any

from aqao_api.db.models import (
    AgentFeedback,
    EvidenceArtifact,
    FailureClassification,
    Requirement,
    TestPlan,
    TestRun,
)
from aqao_api.db.models.failure_classification import FailureCategory
from aqao_api.db.models.requirement import RequirementType
from aqao_api.services.feedback_snapshot import (
    EvidenceStoreSnapshotProvider,
)


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """Minimal session: `.get((type, id))` + a preset `.scalars()` result."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[type, Any], Any] = {}
        self.scalars_rows: list[Any] = []

    def add(self, obj: Any) -> None:
        self._by_key[(type(obj), obj.id)] = obj

    def get(self, model: type, pk: Any) -> Any | None:
        return self._by_key.get((model, pk))

    def scalars(self, _stmt: Any) -> _Scalars:
        return _Scalars(self.scalars_rows)


def _feedback(*, resource_type: str, resource_id: uuid.UUID) -> AgentFeedback:
    return AgentFeedback(
        resource_type=resource_type,
        resource_id=resource_id,
        agent_kind="agent-under-test",
    )


def _provider(session: _FakeSession) -> EvidenceStoreSnapshotProvider:
    return EvidenceStoreSnapshotProvider(session)  # type: ignore[arg-type]


# ---------------------------------------------------- failure_classification


def test_failure_classification_resolver_returns_raw_signal() -> None:
    session = _FakeSession()
    fid = uuid.uuid4()
    session.add(
        FailureClassification(
            id=fid,
            test_run_id=uuid.uuid4(),
            signal_id="sig-42",
            category=FailureCategory.PRODUCT_DEFECT,
            reasoning="500 on checkout",
            raw_signal={"log": "boom", "status": 500},
        )
    )
    snap = _provider(session)(
        _feedback(resource_type="failure_classification", resource_id=fid)
    )
    assert snap["resource_type"] == "failure_classification"
    assert snap["resource_id"] == str(fid)
    assert snap["agent_kind"] == "agent-under-test"
    assert snap["signal_id"] == "sig-42"
    assert snap["raw_signal"] == {"log": "boom", "status": 500}
    assert "snapshot_unavailable" not in snap


# ---------------------------------------------------- test_plan


def test_test_plan_resolver_includes_source_requirement() -> None:
    session = _FakeSession()
    rid = uuid.uuid4()
    pid = uuid.uuid4()
    session.add(
        Requirement(
            id=rid,
            type=RequirementType.USER_STORY,
            source_ref="PR#7",
            commit_sha="abc123",
            raw_payload={"body": "As a user I want checkout"},
            parsed={"acceptance_criteria": ["card is charged"]},
        )
    )
    session.add(TestPlan(id=pid, requirement_id=rid, summary="Checkout plan"))

    snap = _provider(session)(_feedback(resource_type="test_plan", resource_id=pid))
    assert snap["test_plan_summary"] == "Checkout plan"
    req = snap["requirement"]
    assert req["type"] == "user_story"
    assert req["source_ref"] == "PR#7"
    assert req["raw_payload"] == {"body": "As a user I want checkout"}
    assert req["parsed"] == {"acceptance_criteria": ["card is charged"]}


def test_test_plan_resolver_tolerates_missing_requirement() -> None:
    session = _FakeSession()
    pid = uuid.uuid4()
    # Plan present, requirement row gone — should still return the summary.
    session.add(TestPlan(id=pid, requirement_id=uuid.uuid4(), summary="Orphan plan"))
    snap = _provider(session)(_feedback(resource_type="test_plan", resource_id=pid))
    assert snap["test_plan_summary"] == "Orphan plan"
    assert "requirement" not in snap


# ---------------------------------------------------- evidence_report


def test_evidence_report_resolver_gathers_run_context() -> None:
    session = _FakeSession()
    aid = uuid.uuid4()
    run_id = uuid.uuid4()
    pid = uuid.uuid4()
    session.add(
        EvidenceArtifact(
            id=aid,
            test_run_id=run_id,
            metadata_json={"recommendation": "no_go"},
        )
    )
    session.add(TestRun(id=run_id, test_plan_id=pid))
    session.add(TestPlan(id=pid, requirement_id=uuid.uuid4(), summary="Run plan"))
    session.scalars_rows = [
        FailureClassification(
            id=uuid.uuid4(),
            test_run_id=run_id,
            signal_id="sig-1",
            category=FailureCategory.FLAKY_TEST,
            reasoning="timeout",
            raw_signal={},
        )
    ]

    snap = _provider(session)(
        _feedback(resource_type="evidence_report", resource_id=aid)
    )
    assert snap["test_run_id"] == str(run_id)
    assert snap["report_metadata"] == {"recommendation": "no_go"}
    assert snap["test_plan_summary"] == "Run plan"
    assert snap["failures"] == [
        {"signal_id": "sig-1", "category": "flaky_test", "reasoning": "timeout"}
    ]


# ---------------------------------------------------- fallbacks


def test_unknown_resource_type_returns_pointer_only() -> None:
    session = _FakeSession()
    rid = uuid.uuid4()
    snap = _provider(session)(
        _feedback(resource_type="risk_score", resource_id=rid)
    )
    assert snap == {
        "resource_type": "risk_score",
        "resource_id": str(rid),
        "agent_kind": "agent-under-test",
    }


def test_missing_row_flags_snapshot_unavailable() -> None:
    session = _FakeSession()
    rid = uuid.uuid4()
    # Known type, but no row present → pointer + unavailable flag.
    snap = _provider(session)(
        _feedback(resource_type="failure_classification", resource_id=rid)
    )
    assert snap["snapshot_unavailable"] is True
    assert snap["resource_id"] == str(rid)
    assert "raw_signal" not in snap
