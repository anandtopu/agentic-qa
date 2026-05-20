"""Evidence-backed input-snapshot provider for agent feedback — TD-006.

When a thumbs-down is converted into a regression eval case
(:meth:`AgentFeedbackService.convert_to_eval_case`), the case needs the
*inputs* the agent actually saw so a future ``make eval`` run can
reproduce the failure mode. The service takes an
:data:`~aqao_api.services.agent_feedback.InputSnapshotProvider`; the
default returns only the resource pointer, leaving an operator to fill
``inputs`` by hand.

This module replaces that stub in production wiring. It routes by
``resource_type`` to a resolver that pulls the genuine input off the
store that owns it:

* ``failure_classification`` → the row's ``raw_signal`` (literally what
  the classifier was handed) + its ``signal_id``.
* ``test_plan`` → the source :class:`Requirement` (raw + parsed), which
  is what the Planner consumed to produce the plan.
* ``evidence_report`` → the report artifact's run context: the test run,
  its plan summary, and the failure rows the Reporter summarised.

Unknown resource types — or a resource row that has since been pruned —
fall back to the pointer, so conversion never fails on a missing
snapshot. Redaction is applied downstream by ``build_feedback_case``;
resolvers return raw values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_api.db.models import (
    AgentFeedback,
    EvidenceArtifact,
    FailureClassification,
    Requirement,
    TestPlan,
    TestRun,
)

# Canonical resource_type strings the in-product feedback widget emits.
# They mirror the owning table names; anything else falls back to the
# pointer-only snapshot.
RESOURCE_TYPE_TEST_PLAN = "test_plan"
RESOURCE_TYPE_FAILURE_CLASSIFICATION = "failure_classification"
RESOURCE_TYPE_EVIDENCE_REPORT = "evidence_report"

ResourceSnapshotResolver = Callable[[Session, UUID], dict[str, Any] | None]
"""Resolve one resource's agent-input snapshot.

Returns the resolved inputs, or ``None`` when the row no longer exists
(the provider then falls back to the pointer).
"""


def _enum_value(value: Any) -> Any:
    """Return the ``.value`` of an Enum member, else the value unchanged."""
    return value.value if isinstance(value, Enum) else value


def _resolve_failure_classification(
    session: Session, resource_id: UUID
) -> dict[str, Any] | None:
    row = session.get(FailureClassification, resource_id)
    if row is None:
        return None
    return {
        "signal_id": row.signal_id,
        # raw_signal is exactly the payload the classifier was handed.
        "raw_signal": dict(row.raw_signal or {}),
    }


def _resolve_test_plan(session: Session, resource_id: UUID) -> dict[str, Any] | None:
    plan = session.get(TestPlan, resource_id)
    if plan is None:
        return None
    out: dict[str, Any] = {"test_plan_summary": plan.summary}
    requirement = session.get(Requirement, plan.requirement_id)
    if requirement is not None:
        out["requirement"] = {
            "type": _enum_value(requirement.type),
            "source_ref": requirement.source_ref,
            "commit_sha": requirement.commit_sha,
            "raw_payload": dict(requirement.raw_payload or {}),
            "parsed": dict(requirement.parsed or {}),
        }
    return out


def _resolve_evidence_report(
    session: Session, resource_id: UUID
) -> dict[str, Any] | None:
    # An evidence report is addressed by its EvidenceArtifact id.
    artifact = session.get(EvidenceArtifact, resource_id)
    if artifact is None:
        return None
    out: dict[str, Any] = {
        "test_run_id": str(artifact.test_run_id),
        "report_metadata": dict(artifact.metadata_json or {}),
    }
    failures = session.scalars(
        select(FailureClassification)
        .where(FailureClassification.test_run_id == artifact.test_run_id)
        .order_by(FailureClassification.created_at.asc())
    ).all()
    out["failures"] = [
        {
            "signal_id": f.signal_id,
            "category": _enum_value(f.category),
            "reasoning": f.reasoning,
        }
        for f in failures
    ]
    run = session.get(TestRun, artifact.test_run_id)
    if run is not None and run.test_plan_id is not None:
        plan = session.get(TestPlan, run.test_plan_id)
        if plan is not None:
            out["test_plan_summary"] = plan.summary
    return out


DEFAULT_SNAPSHOT_RESOLVERS: dict[str, ResourceSnapshotResolver] = {
    RESOURCE_TYPE_FAILURE_CLASSIFICATION: _resolve_failure_classification,
    RESOURCE_TYPE_TEST_PLAN: _resolve_test_plan,
    RESOURCE_TYPE_EVIDENCE_REPORT: _resolve_evidence_report,
}


class EvidenceStoreSnapshotProvider:
    """An ``InputSnapshotProvider`` backed by the resources' own stores.

    Constructed per request with the tenant-scoped session, so every
    resolver query is RLS-isolated to the caller's tenant.
    """

    def __init__(
        self,
        session: Session,
        *,
        resolvers: Mapping[str, ResourceSnapshotResolver] = DEFAULT_SNAPSHOT_RESOLVERS,
    ) -> None:
        self._session = session
        self._resolvers = resolvers

    def __call__(self, feedback: AgentFeedback) -> dict[str, Any]:
        base: dict[str, Any] = {
            "resource_type": feedback.resource_type,
            "resource_id": str(feedback.resource_id),
            "agent_kind": feedback.agent_kind,
        }
        resolver = self._resolvers.get(feedback.resource_type)
        if resolver is None:
            # Unrecognised resource type — keep the pointer; an operator
            # can fill `inputs` by hand at triage time.
            return base
        resolved = resolver(self._session, feedback.resource_id)
        if resolved is None:
            # The resource row is gone (e.g. pruned by the retention sweep).
            base["snapshot_unavailable"] = True
            return base
        return {**base, **resolved}


__all__ = [
    "DEFAULT_SNAPSHOT_RESOLVERS",
    "RESOURCE_TYPE_EVIDENCE_REPORT",
    "RESOURCE_TYPE_FAILURE_CLASSIFICATION",
    "RESOURCE_TYPE_TEST_PLAN",
    "EvidenceStoreSnapshotProvider",
    "ResourceSnapshotResolver",
]
