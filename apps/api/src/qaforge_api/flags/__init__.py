"""Feature-flag helper.

ADR-0006 + Story 0.4.4: a lightweight wrapper that lets us guard new
user-facing surfaces (DoD #10) without standing up a full feature-flag
service in Phase 0. The default backend is in-memory, populated from the
``QAFORGE_FEATURE_FLAGS`` env var (JSON map) and per-workspace overrides
loaded at request time.

Phase 3 (prompt registry / experiments) will swap the backend to
LaunchDarkly or OpenFeature without touching call sites.
"""

from qaforge_api.flags.client import (
    FeatureFlagClient,
    flag_enabled,
    get_feature_flag_client,
)
from qaforge_api.flags.types import FlagDefinition, FlagRule, FlagStore

__all__ = [
    "FeatureFlagClient",
    "FlagDefinition",
    "FlagRule",
    "FlagStore",
    "flag_enabled",
    "get_feature_flag_client",
]
