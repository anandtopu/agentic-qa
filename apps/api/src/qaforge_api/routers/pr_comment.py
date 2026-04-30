"""PR comment route — Story 1.9.2.

Reuses the EvidenceReportService to assemble the same context the
markdown report uses, then renders the compact PR-comment body. The
GitHub Action POSTs here, takes the returned ``body``, and uses the
``marker`` to find + update an existing comment in place.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from qaforge_agents.reporter import (
    PR_COMMENT_MARKER,
    GoNoGo,
    PrCommentRenderer,
)
from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.db.models import TestPlan, TestRun, Workspace
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.evidence import EvidenceStore, get_evidence_store
from qaforge_api.schemas.pr_comment import PrCommentRequest, PrCommentResponse
from qaforge_api.services.evidence_report import EvidenceReportService

router = APIRouter(tags=["reports"])


def _service(
    session: Session = Depends(tenant_scoped_session),
    store: EvidenceStore = Depends(get_evidence_store),
) -> EvidenceReportService:
    return EvidenceReportService(session, evidence_store=store)


@router.post(
    "/api/v1/test-runs/{test_run_id}/pr-comment",
    response_model=PrCommentResponse,
    summary="Render a compact PR comment body for the GitHub Action",
)
async def render_pr_comment(
    test_run_id: UUID,
    payload: PrCommentRequest,
    service: EvidenceReportService = Depends(_service),
    session: Session = Depends(tenant_scoped_session),
    context: RequestContext = Depends(require_request_context),
) -> PrCommentResponse:
    run = session.get(TestRun, test_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test run not found")

    plan = session.get(TestPlan, run.test_plan_id) if run.test_plan_id else None
    workspace = session.get(Workspace, run.workspace_id)

    # The service has the gather-context logic we need; reuse via a private
    # helper to keep the comment renderer pure.
    report_context = service._build_context(
        run=run,
        plan=plan,
        workspace=workspace,
        recommendation=GoNoGo.NEEDS_REVIEW,
        recommendation_reasoning=_default_recommendation_reason(run),
    )

    renderer = PrCommentRenderer()
    body = renderer.render(
        report_context,
        report_signed_url=payload.report_signed_url,
        run_url=payload.run_url,
    )

    return PrCommentResponse(
        test_run_id=test_run_id,
        body=body,
        marker=PR_COMMENT_MARKER,
    )


def _default_recommendation_reason(run: TestRun) -> str:
    state = run.state.value
    if state == "done":
        return "Run completed; review failures (if any) before merge."
    if state == "failed":
        return "Run failed — check the agent trace and evidence."
    if state == "paused_for_approval":
        return "Approval gate is open — a human needs to review before continuing."
    return f"Run is `{state}`."
