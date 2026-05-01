"""Adapter that bridges :class:`ApprovalService` to the
:class:`aqao_agents.runtime.ApprovalGate` Protocol.

Story 2.1.2 — the workflow runtime lives in ``aqao_agents`` and
must not import from ``aqao_api``. This adapter sits in the API
package and is constructed at request scope; it forwards the runtime's
``request`` / ``lookup`` calls to the real ApprovalService while the
gate context (workflow id, correlation id) is folded back onto an
``approval_requests`` row.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from aqao_agents.runtime.approval import ApprovalDecision
from aqao_api.auth.context import RequestContext
from aqao_api.services.approval import ApprovalService


class ApprovalServiceGateAdapter:
    """Adapt ``ApprovalService`` to the runtime's ApprovalGate Protocol."""

    def __init__(self, *, service: ApprovalService, context: RequestContext) -> None:
        self._service = service
        self._context = context

    def request(
        self,
        *,
        workflow_id: UUID,
        workspace_id: UUID,
        event_type: str,
        subject: str,
        reason: str | None,
        gate_context: Mapping[str, Any],
    ) -> UUID:
        record = self._service.request(
            event_type=event_type,
            subject=subject,
            context=self._context,
            workspace_id=workspace_id,
            reason=reason,
            gate_context={**dict(gate_context), "workflow_id": str(workflow_id)},
        )
        return record.id

    def lookup(self, request_id: UUID) -> ApprovalDecision:
        record = self._service.get(request_id=request_id)
        return ApprovalDecision(
            request_id=record.id,
            state=record.state,
            decided_by=record.decided_by,
            decided_at=record.decided_at,
            comment=record.decision_comment,
        )


__all__ = ["ApprovalServiceGateAdapter"]
