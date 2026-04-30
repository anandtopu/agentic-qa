"""Unit tests for the prompt registry — Story 3.4.1.

Verifies:

* Versions are sorted by semver, ``latest()`` returns the highest.
* Duplicate / wrong-agent versions are rejected at construction.
* ``resolve(None)`` returns latest; ``resolve("missing")`` raises.
* Pre-release ordering: ``1.0.0-rc.1`` sorts before ``1.0.0``.
"""

from __future__ import annotations

import pytest

from qaforge_agents.prompts import (
    PromptRegistry,
    PromptVersion,
    UnknownPromptVersion,
    parse_semver,
)


def _v(version: str, *, agent: str = "planner", system: str = "...") -> PromptVersion:
    return PromptVersion(agent=agent, version=version, system=system)


def test_versions_are_sorted_ascending_and_latest_is_last() -> None:
    registry = PromptRegistry.of(
        agent="planner",
        versions=[_v("1.2.0"), _v("1.0.0"), _v("1.10.0"), _v("1.2.1")],
    )
    actual = [v.version for v in registry.versions]
    assert actual == ["1.0.0", "1.2.0", "1.2.1", "1.10.0"]
    assert registry.latest().version == "1.10.0"


def test_resolve_none_returns_latest() -> None:
    registry = PromptRegistry.of(agent="planner", versions=[_v("1.0.0"), _v("2.0.0")])
    assert registry.resolve(None).version == "2.0.0"


def test_resolve_unknown_raises() -> None:
    registry = PromptRegistry.of(agent="planner", versions=[_v("1.0.0")])
    with pytest.raises(UnknownPromptVersion) as exc:
        registry.resolve("9.9.9")
    assert exc.value.agent == "planner"
    assert exc.value.version == "9.9.9"


def test_duplicate_versions_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        PromptRegistry.of(
            agent="planner",
            versions=[_v("1.0.0"), _v("1.0.0", system="other")],
        )


def test_wrong_agent_rejected() -> None:
    with pytest.raises(ValueError, match="not 'planner'"):
        PromptRegistry.of(
            agent="planner",
            versions=[_v("1.0.0", agent="api_tester")],
        )


def test_invalid_semver_rejected_at_version_construction() -> None:
    with pytest.raises(ValueError, match="not a semver"):
        PromptVersion(agent="planner", version="latest", system="...")


def test_prerelease_sorts_before_release() -> None:
    registry = PromptRegistry.of(
        agent="planner",
        versions=[_v("1.0.0"), _v("1.0.0-rc.1"), _v("1.0.0-rc.2")],
    )
    actual = [v.version for v in registry.versions]
    assert actual == ["1.0.0-rc.1", "1.0.0-rc.2", "1.0.0"]


def test_parse_semver_round_trips_simple_release() -> None:
    assert parse_semver("2.3.4")[:3] == (2, 3, 4)


def test_has_version_check() -> None:
    registry = PromptRegistry.of(agent="planner", versions=[_v("1.0.0")])
    assert registry.has_version("1.0.0")
    assert not registry.has_version("2.0.0")


def test_empty_registry_latest_raises() -> None:
    registry = PromptRegistry.of(agent="planner", versions=[])
    with pytest.raises(UnknownPromptVersion):
        registry.latest()
