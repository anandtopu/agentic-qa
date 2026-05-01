"""Feature-flag data model."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class FlagRule(BaseModel):
    """Per-workspace override for a flag's default value."""

    workspace_id: UUID
    enabled: bool


class FlagDefinition(BaseModel):
    """A single feature flag.

    ``default`` applies when no workspace rule matches. ``rules`` are
    evaluated in order — first match wins.
    """

    name: str
    default: bool = False
    description: str = ""
    rules: list[FlagRule] = Field(default_factory=list)

    def evaluate(self, workspace_id: UUID | None) -> bool:
        if workspace_id is not None:
            for rule in self.rules:
                if rule.workspace_id == workspace_id:
                    return rule.enabled
        return self.default


class FlagStore(Protocol):
    """Backend for flag storage. Implementations may be in-memory or DB-backed."""

    def get(self, name: str) -> FlagDefinition | None: ...
    def upsert(self, definition: FlagDefinition) -> None: ...
    def all_flags(self) -> list[FlagDefinition]: ...
