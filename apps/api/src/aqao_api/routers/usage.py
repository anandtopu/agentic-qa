"""Usage / cost summary route — Story 2.5.2."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.usage import UsageBucketResponse, UsageSummaryResponse
from aqao_api.services.usage_query import UsageQueryService

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


def _service(session: Session = Depends(tenant_scoped_session)) -> UsageQueryService:
    return UsageQueryService(session)


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    summary="Aggregate cost / token / call counts (tenant-scoped)",
)
def usage_summary(
    workspace_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    service: UsageQueryService = Depends(_service),
    _ctx: RequestContext = Depends(require_request_context),
) -> UsageSummaryResponse:
    summary = service.summary(workspace_id=workspace_id, since=since, until=until)
    return UsageSummaryResponse(
        total_usd_cost=summary.total_usd_cost,
        total_prompt_tokens=summary.total_prompt_tokens,
        total_completion_tokens=summary.total_completion_tokens,
        total_calls=summary.total_calls,
        by_agent=[
            UsageBucketResponse(
                label=b.label,
                usd_cost=b.usd_cost,
                prompt_tokens=b.prompt_tokens,
                completion_tokens=b.completion_tokens,
                call_count=b.call_count,
            )
            for b in summary.by_agent
        ],
        by_provider=[
            UsageBucketResponse(
                label=b.label,
                usd_cost=b.usd_cost,
                prompt_tokens=b.prompt_tokens,
                completion_tokens=b.completion_tokens,
                call_count=b.call_count,
            )
            for b in summary.by_provider
        ],
        since=summary.since,
        until=summary.until,
    )
