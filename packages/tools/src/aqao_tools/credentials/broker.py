"""Credential broker implementations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from aqao_redaction import Redactor, default_redactor


@dataclass(slots=True)
class SecretBundle:
    """Resolved secrets for a single tool run.

    The bundle wraps the resolved key/value pairs **and** a per-run
    :class:`Redactor` that knows how to scrub the values from any text
    a tool might emit. Pass ``redactor`` to anything that logs, persists
    evidence, or returns output to the user.
    """

    workspace_id: UUID
    environment: str
    values: dict[str, str] = field(default_factory=dict)
    redactor: Redactor = field(default_factory=default_redactor)

    def env_dict(self) -> dict[str, str]:
        return dict(self.values)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self.values.items())


class CredentialBroker(Protocol):
    """Resolves per-workspace, per-environment secrets for a tool run."""

    async def issue(
        self,
        *,
        workspace_id: UUID,
        environment: str,
        keys: Iterable[str] | None = None,
    ) -> SecretBundle: ...


class InMemoryCredentialBroker:
    """Phase 1 broker backed by a dict-of-dicts.

    Use :meth:`load_workspace` to seed values from the Control Plane's
    ``WorkspaceEnvironment.variables`` mapping (Story 1.1.3). The broker
    automatically registers every issued value with the workspace
    redactor so logs / evidence get stripped of them.
    """

    def __init__(self, *, redactor: Redactor | None = None) -> None:
        self._store: dict[tuple[UUID, str], dict[str, str]] = {}
        self._redactor = redactor or default_redactor()

    def load_workspace(
        self,
        *,
        workspace_id: UUID,
        environment: str,
        variables: Mapping[str, str],
    ) -> None:
        self._store[(workspace_id, environment)] = dict(variables)

    async def issue(
        self,
        *,
        workspace_id: UUID,
        environment: str,
        keys: Iterable[str] | None = None,
    ) -> SecretBundle:
        all_values = self._store.get((workspace_id, environment), {})
        if keys is None:
            selected = dict(all_values)
        else:
            selected = {k: all_values[k] for k in keys if k in all_values}

        run_redactor = self._redactor.with_extra(
            strings=tuple(v for v in selected.values() if v),
        )
        return SecretBundle(
            workspace_id=workspace_id,
            environment=environment,
            values=selected,
            redactor=run_redactor,
        )

    @contextmanager
    def temporary(
        self,
        *,
        workspace_id: UUID,
        environment: str,
        variables: Mapping[str, str],
    ) -> Iterator[None]:
        """Test/dev helper — load and clear within a `with` block."""
        previous = self._store.get((workspace_id, environment))
        self.load_workspace(
            workspace_id=workspace_id,
            environment=environment,
            variables=variables,
        )
        try:
            yield None
        finally:
            if previous is None:
                self._store.pop((workspace_id, environment), None)
            else:
                self._store[(workspace_id, environment)] = previous
