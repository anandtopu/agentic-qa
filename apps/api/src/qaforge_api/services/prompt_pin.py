"""PromptPinService — Story 3.4.1.

Workspace-level pin from ``(workspace, agent)`` to a prompt version.
Used by:

* the agent-invocation path to resolve "what version do we run?";
* the API surface (``/api/v1/workspaces/{id}/prompts/{agent}``) for
  ops to view + change pins;
* Story 3.4.2's experiment-promotion flow which calls ``set_pin``
  with the winning variant once the experiment closes.

Every transition is mirrored into the audit log so it's recoverable
who pinned what and when.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import PromptPin
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError


class PromptPinService:
    """Single write path for ``prompt_pins``."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    def list_pins(self, *, workspace_id: UUID) -> list[PromptPin]:
        stmt = (
            select(PromptPin)
            .where(PromptPin.workspace_id == workspace_id)
            .order_by(PromptPin.agent_name.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get_pin(self, *, workspace_id: UUID, agent_name: str) -> PromptPin:
        stmt = select(PromptPin).where(
            PromptPin.workspace_id == workspace_id,
            PromptPin.agent_name == agent_name,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            raise ResourceNotFoundError("prompt_pin", (workspace_id, agent_name))
        return row

    def get_pinned_version(self, *, workspace_id: UUID, agent_name: str) -> str | None:
        """Return the pinned version, or ``None`` if no pin exists.

        Callers fall back to the in-code registry's ``latest()`` when
        this returns ``None`` — the absence of a pin is the explicit
        opt-in to "track latest".
        """
        try:
            return self.get_pin(workspace_id=workspace_id, agent_name=agent_name).version
        except ResourceNotFoundError:
            return None

    def set_pin(
        self,
        *,
        workspace_id: UUID,
        agent_name: str,
        version: str,
        context: RequestContext,
        note: str | None = None,
        action: str = "prompt_pin.set",
    ) -> PromptPin:
        """Pin (or re-pin) ``(workspace, agent)`` to ``version``.

        The action key on the audit row defaults to ``prompt_pin.set``;
        Story 3.4.2's promotion flow passes ``prompt_pin.promote`` so
        downstream consumers can distinguish a manual pin from an
        experiment winner.
        """
        existing: PromptPin | None
        try:
            existing = self.get_pin(workspace_id=workspace_id, agent_name=agent_name)
        except ResourceNotFoundError:
            existing = None

        if existing is None:
            pin = PromptPin(
                tenant_id=context.tenant_id,
                workspace_id=workspace_id,
                agent_name=agent_name,
                version=version,
                pinned_by=context.user_id,
                note=note,
            )
            self._session.add(pin)
        else:
            existing.version = version
            existing.pinned_by = context.user_id
            existing.note = note
            pin = existing
        self._session.flush()

        self._audit.record(
            context=context,
            action=action,
            resource_type="prompt_pin",
            resource_id=pin.id,
            payload={
                "workspace_id": str(workspace_id),
                "agent_name": agent_name,
                "version": version,
                "note": note,
            },
        )
        return pin

    def delete_pin(
        self,
        *,
        workspace_id: UUID,
        agent_name: str,
        context: RequestContext,
    ) -> None:
        pin = self.get_pin(workspace_id=workspace_id, agent_name=agent_name)
        self._session.delete(pin)
        self._audit.record(
            context=context,
            action="prompt_pin.delete",
            resource_type="prompt_pin",
            resource_id=pin.id,
            payload={
                "workspace_id": str(workspace_id),
                "agent_name": agent_name,
            },
        )


__all__ = ["PromptPinService"]
