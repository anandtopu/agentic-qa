"""Flakiness routes — Story 3.3.1.

PRD §13 surface: ``/api/v1/workspaces/{id}/flakiness/{test_id}``.
The Phase-3 admin UI hits this for the test-detail flakiness panel;
the classifier (Story 3.3.2) reads the same data via
:class:`FlakinessService` directly, in-process.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aqao_api.auth import Permission, require_permission
from aqao_api.auth.context import RequestContext
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.flakiness import (
    FlakinessSummaryResponse,
    FlakinessWindowResponse,
)
from aqao_api.services.flakiness import FlakinessService

router = APIRouter(prefix="/api/v1/workspaces", tags=["flakiness"])


def _service(session: Session = Depends(tenant_scoped_session)) -> FlakinessService:
    return FlakinessService(session)


@router.get(
    "/{workspace_id}/flakiness/{test_id:path}",
    response_model=FlakinessSummaryResponse,
    summary="Rolling 14 / 30 / 90-day flakiness for one test_id.",
)
def get_flakiness(
    workspace_id: UUID,
    test_id: str,
    service: FlakinessService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.TEST_RUN_VIEW)),
) -> FlakinessSummaryResponse:
    summary = service.summary(workspace_id=workspace_id, test_id=test_id)
    return FlakinessSummaryResponse(
        test_id=summary.test_id,
        workspace_id=summary.workspace_id,
        flakiness_score=summary.flakiness_score,
        windows=[FlakinessWindowResponse(**w.to_dict()) for w in summary.windows],
    )
