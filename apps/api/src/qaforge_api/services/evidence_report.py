"""EvidenceReportService — Story 1.8.

Gathers a test_run + its agent_tasks + failure_classifications into a
:class:`RunReportContext`, renders Markdown via the reporter, persists
the resulting bytes through :class:`EvidenceStore`, and records an
``evidence_artifacts`` row that downstream surfaces (PR comment, UI)
can reference by id.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_agents.reporter import (
    AgentTraceLine,
    ArtifactSummary,
    FailureSummary,
    GoNoGo,
    MarkdownReportRenderer,
    RunReportContext,
    TestCaseSummary,
)
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    AgentTask,
    EvidenceArtifact,
    FailureClassification,
    TestCase,
    TestPlan,
    TestRun,
    Workspace,
)
from qaforge_api.evidence import EvidenceStore
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError

REPORT_FILENAME = "run_report.md"
REPORT_CONTENT_TYPE = "text/markdown"


@dataclass(slots=True)
class GeneratedReport:
    artifact: EvidenceArtifact
    markdown: str
    signed_url: str | None
    signed_url_expires_at: datetime | None


class EvidenceReportService:
    def __init__(
        self,
        session: Session,
        *,
        evidence_store: EvidenceStore,
        renderer: MarkdownReportRenderer | None = None,
    ) -> None:
        self._session = session
        self._store = evidence_store
        self._renderer = renderer or MarkdownReportRenderer()
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def latest_for_run(self, test_run_id: UUID) -> EvidenceArtifact | None:
        stmt = (
            select(EvidenceArtifact)
            .where(
                EvidenceArtifact.test_run_id == test_run_id,
                EvidenceArtifact.original_filename == REPORT_FILENAME,
            )
            .order_by(EvidenceArtifact.created_at.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    async def fetch_latest(
        self,
        *,
        test_run_id: UUID,
        context: RequestContext,
    ) -> GeneratedReport:
        run = self._session.get(TestRun, test_run_id)
        if run is None:
            raise ResourceNotFoundError("test_run", test_run_id)

        artifact = self.latest_for_run(test_run_id)
        if artifact is None:
            raise ResourceNotFoundError("evidence_report", test_run_id)

        body = await self._store.get_bytes(storage_key=artifact.storage_key)
        signed = await self._store.signed_url(storage_key=artifact.storage_key)

        self._audit.record(
            context=context,
            action="evidence_report.accessed",
            resource_type="evidence_artifact",
            resource_id=artifact.id,
            payload={"test_run_id": str(test_run_id)},
        )
        return GeneratedReport(
            artifact=artifact,
            markdown=body.decode("utf-8"),
            signed_url=signed.url,
            signed_url_expires_at=signed.expires_at,
        )

    # --- mutations --------------------------------------------------------------

    async def generate(
        self,
        *,
        test_run_id: UUID,
        context: RequestContext,
        recommendation: GoNoGo = GoNoGo.NEEDS_REVIEW,
        recommendation_reasoning: str = "",
    ) -> GeneratedReport:
        run = self._session.get(TestRun, test_run_id)
        if run is None:
            raise ResourceNotFoundError("test_run", test_run_id)

        plan = self._session.get(TestPlan, run.test_plan_id) if run.test_plan_id else None
        workspace = self._session.get(Workspace, run.workspace_id)

        report_context = self._build_context(
            run=run,
            plan=plan,
            workspace=workspace,
            recommendation=recommendation,
            recommendation_reasoning=recommendation_reasoning,
        )
        markdown = self._renderer.render(report_context)
        body = markdown.encode("utf-8")
        sha256 = hashlib.sha256(body).hexdigest()

        result = await self._store.put(
            tenant_id=context.tenant_id,
            workspace_id=run.workspace_id,
            run_id=run.id,
            body=body,
            content_type=REPORT_CONTENT_TYPE,
            original_filename=REPORT_FILENAME,
            declared_sha256=sha256,
        )

        artifact = EvidenceArtifact(
            tenant_id=context.tenant_id,
            test_run_id=run.id,
            agent_task_id=None,
            sha256=result.metadata.sha256,
            content_type=result.metadata.content_type,
            size_bytes=result.metadata.size_bytes,
            storage_key=result.storage_key,
            original_filename=result.metadata.original_filename,
            metadata_json={
                "template_version": report_context.template_version,
                "recommendation": report_context.recommendation.value,
            },
        )
        self._session.add(artifact)
        self._session.flush()

        signed = await self._store.signed_url(storage_key=result.storage_key)

        self._audit.record(
            context=context,
            action="evidence_report.generated",
            resource_type="evidence_artifact",
            resource_id=artifact.id,
            payload={
                "test_run_id": str(run.id),
                "sha256": result.metadata.sha256,
                "size_bytes": result.metadata.size_bytes,
                "template_version": report_context.template_version,
                "recommendation": report_context.recommendation.value,
            },
        )
        return GeneratedReport(
            artifact=artifact,
            markdown=markdown,
            signed_url=signed.url,
            signed_url_expires_at=signed.expires_at,
        )

    # --- helpers ----------------------------------------------------------------

    def _build_context(
        self,
        *,
        run: TestRun,
        plan: TestPlan | None,
        workspace: Workspace | None,
        recommendation: GoNoGo,
        recommendation_reasoning: str,
    ) -> RunReportContext:
        agent_tasks = self._fetch_agent_tasks(run.id)
        failure_rows = self._fetch_failures(run.id)
        test_cases = self._fetch_test_cases(plan.id) if plan is not None else []

        total_latency_ms = sum(t.duration_ms for t in agent_tasks)

        failure_summaries = [
            FailureSummary(
                signal_id=row.signal_id,
                category=row.category.value,
                confidence=row.confidence,
                classified_by=row.classified_by.value,
                rule=row.rule,
                reasoning=row.reasoning,
                suggested_fix=row.suggested_fix,
            )
            for row in failure_rows
        ]
        category_counts: dict[str, int] = {}
        heuristic_count = 0
        for row in failure_rows:
            category_counts[row.category.value] = category_counts.get(row.category.value, 0) + 1
            if row.classified_by.value == "heuristic":
                heuristic_count += 1
        heuristic_ratio = (
            (Decimal(heuristic_count) / Decimal(len(failure_rows))).quantize(Decimal("0.01"))
            if failure_rows
            else Decimal("0")
        )

        agent_trace = [
            AgentTraceLine(
                step_index=t.step_index,
                agent_name=t.agent_name,
                state=t.state.value,
                duration_ms=t.duration_ms,
                attempt=t.attempt,
                error_excerpt=_excerpt(t.error),
            )
            for t in agent_tasks
        ]

        case_summaries = [
            TestCaseSummary(
                title=tc.title,
                type=tc.type.value,
                priority=tc.priority.value,
                automation_candidate=tc.automation_candidate,
                status="pending",  # populated when test_results land in 1.6 follow-up
            )
            for tc in test_cases
        ]

        duration_ms = 0
        if run.started_at is not None and run.finished_at is not None:
            duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)

        return RunReportContext(
            workspace_name=workspace.name if workspace is not None else "—",
            test_run_id=run.id,
            test_plan_summary=plan.summary if plan is not None else "",
            state=run.state.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=duration_ms,
            coverage_areas=[],
            test_cases=case_summaries,
            total=len(case_summaries),
            passed=0,
            failed=len(failure_rows),
            skipped=0,
            failures=failure_summaries,
            failure_category_counts=category_counts,
            heuristic_ratio=heuristic_ratio,
            risk_score=None,
            risk_drivers=[],
            artifacts=self._artifact_summaries_for(run.id),
            agent_trace=agent_trace,
            total_usd_cost_cents=int(plan.usd_cost) if plan is not None else 0,
            total_latency_ms=total_latency_ms,
            open_questions=list(plan.open_questions) if plan is not None else [],
            approvals=[],
            recommendation=recommendation,
            recommendation_reasoning=recommendation_reasoning,
            generated_at=datetime.now(UTC),
        )

    def _fetch_agent_tasks(self, run_id: UUID) -> Sequence[AgentTask]:
        return list(
            self._session.scalars(
                select(AgentTask)
                .where(AgentTask.test_run_id == run_id)
                .order_by(AgentTask.step_index.asc())
            ).all()
        )

    def _fetch_failures(self, run_id: UUID) -> Sequence[FailureClassification]:
        return list(
            self._session.scalars(
                select(FailureClassification)
                .where(FailureClassification.test_run_id == run_id)
                .order_by(FailureClassification.created_at.asc())
            ).all()
        )

    def _fetch_test_cases(self, plan_id: UUID) -> Sequence[TestCase]:
        return list(
            self._session.scalars(
                select(TestCase)
                .where(TestCase.test_plan_id == plan_id)
                .order_by(TestCase.created_at.asc())
            ).all()
        )

    def _artifact_summaries_for(self, run_id: UUID) -> list[ArtifactSummary]:
        rows = list(
            self._session.scalars(
                select(EvidenceArtifact)
                .where(EvidenceArtifact.test_run_id == run_id)
                .order_by(EvidenceArtifact.created_at.asc())
            ).all()
        )
        return [
            ArtifactSummary(
                kind=_kind_for(row.original_filename),
                filename=row.original_filename,
                sha256=row.sha256,
                size_bytes=row.size_bytes,
                signed_url=None,
                signed_url_expires_at=None,
            )
            for row in rows
        ]


def _excerpt(text: str | None, *, limit: int = 200) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _kind_for(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".zip") or "trace" in name:
        return "trace"
    if name.endswith((".webm", ".mp4")):
        return "video"
    if name.endswith((".png", ".jpg", ".jpeg")):
        return "screenshot"
    if name.endswith(".md"):
        return "report"
    return "other"


def _shape_audit(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(items)
