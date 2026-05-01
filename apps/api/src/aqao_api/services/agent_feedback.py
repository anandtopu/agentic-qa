"""AgentFeedbackService — Story 6.3.1.

Records thumbs up/down on any agent output and converts negative
feedback into regression cases under
``packages/eval/datasets/<agent_kind>/feedback_cases.jsonl``.

The service is the single write path for ``agent_feedback`` rows:

* :meth:`record` — append one feedback signal + audit event.
* :meth:`query` — read filtered slices of the ledger.
* :meth:`weekly_review` — roll up the past N days into the
  low-rated-review summary the eng-lead consumes every Monday.
* :meth:`convert_to_eval_case` — turn a single negatively-rated
  feedback row into a JSONL line under the agent's feedback
  dataset; idempotent on case id.

The eval base directory and the original-input snapshot loader are
injected so tests can point at a temp directory and stub the input
provider, and so the production wiring can pull the snapshot from
whichever evidence source the resource lives in.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import AgentFeedback, FeedbackRating
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError
from aqao_eval.feedback_cases import (
    FeedbackCaseAppendResult,
    append_feedback_case,
    build_feedback_case,
)

DEFAULT_REVIEW_WINDOW = timedelta(days=7)


@dataclass(slots=True, frozen=True)
class AgentReviewSlice:
    """One agent's slice of :class:`WeeklyReview`."""

    agent_kind: str
    total_feedback: int
    down_count: int
    up_count: int
    pending_conversion: int
    converted: int

    @property
    def down_rate(self) -> float:
        if self.total_feedback == 0:
            return 0.0
        return self.down_count / self.total_feedback

    @property
    def conversion_rate(self) -> float:
        if self.down_count == 0:
            return 0.0
        return self.converted / self.down_count


@dataclass(slots=True, frozen=True)
class WeeklyReview:
    """Rolling low-rated review summary."""

    workspace_id: UUID
    window_days: int
    since: datetime
    overall_total: int
    overall_down_count: int
    overall_converted: int
    by_agent: tuple[AgentReviewSlice, ...]
    pending_items: tuple[AgentFeedback, ...]

    @property
    def overall_conversion_rate(self) -> float:
        if self.overall_down_count == 0:
            return 0.0
        return self.overall_converted / self.overall_down_count


@dataclass(slots=True, frozen=True)
class ConversionOutcome:
    """Outcome of :meth:`AgentFeedbackService.convert_to_eval_case`."""

    feedback: AgentFeedback
    append_result: FeedbackCaseAppendResult


InputSnapshotProvider = Callable[[AgentFeedback], dict[str, Any]]
"""Resolve the original prompt/context that produced an agent output.

The service does not assume which evidence store carries the snapshot;
production wiring will route by ``resource_type`` (test plan rows,
classification rows, evidence reports). For now the default provider
returns the resource pointer so a hand-triage operator can fill in
the rest, but tests can inject a deterministic stub.
"""


def _default_snapshot_provider(feedback: AgentFeedback) -> dict[str, Any]:
    return {
        "resource_type": feedback.resource_type,
        "resource_id": str(feedback.resource_id),
        "agent_kind": feedback.agent_kind,
    }


class AgentFeedbackService:
    """Single write + read point for the agent_feedback ledger."""

    def __init__(
        self,
        session: Session,
        *,
        audit: AuditService | None = None,
        eval_dataset_dir: Path,
        snapshot_provider: InputSnapshotProvider | None = None,
        redact: Callable[[str], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._audit = audit
        self._eval_dataset_dir = eval_dataset_dir
        self._snapshot_provider = snapshot_provider or _default_snapshot_provider
        self._redact = redact
        self._clock = clock or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------ writes

    def record(
        self,
        *,
        context: RequestContext,
        workspace_id: UUID,
        agent_kind: str,
        resource_type: str,
        resource_id: UUID,
        rating: FeedbackRating,
        comment: str | None,
    ) -> AgentFeedback:
        row = AgentFeedback(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            agent_kind=agent_kind,
            resource_type=resource_type,
            resource_id=resource_id,
            rating=rating.value,
            comment=comment,
            submitted_by_user_id=context.user_id,
            submitted_at=self._clock(),
        )
        self._session.add(row)
        self._session.flush()
        if self._audit is not None:
            self._audit.record(
                context=context,
                action="agent_feedback.recorded",
                resource_type="agent_feedback",
                resource_id=row.id,
                payload={
                    "agent_kind": agent_kind,
                    "rating": rating.value,
                    "target_resource_type": resource_type,
                    "target_resource_id": str(resource_id),
                },
            )
        return row

    def convert_to_eval_case(
        self,
        *,
        context: RequestContext,
        feedback_id: UUID,
        expected: dict[str, Any] | None = None,
    ) -> ConversionOutcome:
        row = self._session.get(AgentFeedback, feedback_id)
        if row is None:
            raise ResourceNotFoundError("agent_feedback", feedback_id)
        if row.rating != FeedbackRating.DOWN.value:
            raise FeedbackNotConvertibleError(feedback_id, row.rating)

        case = build_feedback_case(
            feedback_id=row.id,
            agent_kind=row.agent_kind,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            workspace_id=row.workspace_id,
            submitted_at=row.submitted_at,
            inputs=self._snapshot_provider(row),
            expected=expected,
            comment=row.comment,
            redact=self._redact,
        )
        result = append_feedback_case(
            base_dir=self._eval_dataset_dir,
            case=case,
            agent_kind=row.agent_kind,
        )
        # Idempotent: even if the line was already present, re-record
        # the link on the row in case the previous attempt failed mid-write.
        row.eval_case_id = result.case_id
        row.eval_case_path = result.relative_path
        if row.converted_at is None:
            row.converted_at = self._clock()
        self._session.flush()
        if self._audit is not None and result.created:
            self._audit.record(
                context=context,
                action="agent_feedback.converted_to_eval_case",
                resource_type="agent_feedback",
                resource_id=row.id,
                payload={
                    "agent_kind": row.agent_kind,
                    "eval_case_id": result.case_id,
                    "eval_case_path": result.relative_path,
                },
            )
        return ConversionOutcome(feedback=row, append_result=result)

    # ------------------------------------------------------------ reads

    def query(
        self,
        *,
        workspace_id: UUID,
        agent_kind: str | None = None,
        rating: FeedbackRating | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AgentFeedback]:
        stmt = select(AgentFeedback).where(AgentFeedback.workspace_id == workspace_id)
        if agent_kind is not None:
            stmt = stmt.where(AgentFeedback.agent_kind == agent_kind)
        if rating is not None:
            stmt = stmt.where(AgentFeedback.rating == rating.value)
        if since is not None:
            stmt = stmt.where(AgentFeedback.submitted_at >= since)
        stmt = stmt.order_by(AgentFeedback.submitted_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())

    def weekly_review(
        self,
        *,
        workspace_id: UUID,
        window: timedelta = DEFAULT_REVIEW_WINDOW,
        now: datetime | None = None,
        pending_limit: int = 25,
    ) -> WeeklyReview:
        moment = now or self._clock()
        since = moment - window

        # Per-agent rollup. Computed in Python rather than SQL because the
        # row counts are bounded (a workspace generating > 10k feedback
        # signals/week would surface as a separate operational concern,
        # and the in-Python path is portable across SQLite test setups
        # that don't speak the FILTER clause).
        rows = self.query(workspace_id=workspace_id, since=since, limit=10_000)
        by_agent: dict[str, dict[str, int]] = {}
        for row in rows:
            slot = by_agent.setdefault(
                row.agent_kind,
                {"total": 0, "down": 0, "up": 0, "converted": 0, "pending": 0},
            )
            slot["total"] += 1
            if row.rating == FeedbackRating.DOWN.value:
                slot["down"] += 1
                if row.converted_at is not None:
                    slot["converted"] += 1
                else:
                    slot["pending"] += 1
            elif row.rating == FeedbackRating.UP.value:
                slot["up"] += 1

        slices = tuple(
            AgentReviewSlice(
                agent_kind=kind,
                total_feedback=stats["total"],
                down_count=stats["down"],
                up_count=stats["up"],
                pending_conversion=stats["pending"],
                converted=stats["converted"],
            )
            for kind, stats in sorted(by_agent.items())
        )
        overall_total = sum(s.total_feedback for s in slices)
        overall_down = sum(s.down_count for s in slices)
        overall_converted = sum(s.converted for s in slices)

        # Pending = thumbs-down rows whose conversion hasn't fired yet.
        pending_stmt = (
            select(AgentFeedback)
            .where(
                AgentFeedback.workspace_id == workspace_id,
                AgentFeedback.rating == FeedbackRating.DOWN.value,
                AgentFeedback.converted_at.is_(None),
                AgentFeedback.submitted_at >= since,
            )
            .order_by(AgentFeedback.submitted_at.asc())
            .limit(pending_limit)
        )
        pending = tuple(self._session.scalars(pending_stmt).all())

        return WeeklyReview(
            workspace_id=workspace_id,
            window_days=int(window.total_seconds() // 86400) or 1,
            since=since,
            overall_total=overall_total,
            overall_down_count=overall_down,
            overall_converted=overall_converted,
            by_agent=slices,
            pending_items=pending,
        )

    def get(self, feedback_id: UUID) -> AgentFeedback:
        row = self._session.get(AgentFeedback, feedback_id)
        if row is None:
            raise ResourceNotFoundError("agent_feedback", feedback_id)
        return row

    # ----------------------------------------------------- diagnostics

    def total_in_window(
        self, *, workspace_id: UUID, since: datetime
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AgentFeedback)
            .where(
                AgentFeedback.workspace_id == workspace_id,
                AgentFeedback.submitted_at >= since,
            )
        )
        return int(self._session.scalar(stmt) or 0)


class FeedbackNotConvertibleError(Exception):
    """Raised when convert_to_eval_case is called on non-DOWN feedback."""

    def __init__(self, feedback_id: UUID, rating: str) -> None:
        super().__init__(
            f"feedback {feedback_id} has rating {rating!r}; only 'down' feedback can be converted"
        )
        self.feedback_id = feedback_id
        self.rating = rating


__all__ = [
    "DEFAULT_REVIEW_WINDOW",
    "AgentFeedbackService",
    "AgentReviewSlice",
    "ConversionOutcome",
    "FeedbackNotConvertibleError",
    "InputSnapshotProvider",
    "WeeklyReview",
]
