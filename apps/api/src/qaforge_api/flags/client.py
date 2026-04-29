"""FeatureFlagClient and the ``flag_enabled`` helper."""

from __future__ import annotations

import os
from functools import lru_cache
from uuid import UUID

import structlog

from qaforge_api.flags.store import InMemoryFlagStore
from qaforge_api.flags.types import FlagStore

_FLAGS_ENV_VAR = "QAFORGE_FEATURE_FLAGS"


class FeatureFlagClient:
    """Evaluate flags against a workspace.

    Unknown flags evaluate to ``False`` and emit a warning log so a typo
    in code doesn't silently leak unfinished features.
    """

    def __init__(self, store: FlagStore) -> None:
        self._store = store
        self._log = structlog.get_logger("qaforge_api.flags")

    def is_enabled(self, name: str, workspace_id: UUID | None = None) -> bool:
        definition = self._store.get(name)
        if definition is None:
            self._log.warning("flags.unknown", flag=name)
            return False
        return definition.evaluate(workspace_id)

    @property
    def store(self) -> FlagStore:
        return self._store


@lru_cache(maxsize=1)
def get_feature_flag_client() -> FeatureFlagClient:
    """Process-wide singleton built from the ``QAFORGE_FEATURE_FLAGS`` env var."""
    store = InMemoryFlagStore.from_env_json(os.getenv(_FLAGS_ENV_VAR))
    return FeatureFlagClient(store)


def flag_enabled(name: str, workspace_id: UUID | None = None) -> bool:
    """Module-level convenience used in non-injected call sites."""
    return get_feature_flag_client().is_enabled(name, workspace_id)
