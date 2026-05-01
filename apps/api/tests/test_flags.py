from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from aqao_api.flags.client import FeatureFlagClient, get_feature_flag_client
from aqao_api.flags.store import InMemoryFlagStore
from aqao_api.flags.types import FlagDefinition, FlagRule

WORKSPACE_A = UUID("00000000-0000-0000-0000-00000000000a")
WORKSPACE_B = UUID("00000000-0000-0000-0000-00000000000b")


def _client(*defs: FlagDefinition) -> FeatureFlagClient:
    return FeatureFlagClient(InMemoryFlagStore(list(defs)))


def test_unknown_flag_is_disabled() -> None:
    client = _client()
    assert client.is_enabled("does-not-exist") is False


def test_default_value_returned_when_no_rules_match() -> None:
    client = _client(FlagDefinition(name="ui_v2", default=True))
    assert client.is_enabled("ui_v2") is True
    assert client.is_enabled("ui_v2", workspace_id=uuid4()) is True


def test_workspace_rule_overrides_default() -> None:
    client = _client(
        FlagDefinition(
            name="planner_v2",
            default=False,
            rules=[FlagRule(workspace_id=WORKSPACE_A, enabled=True)],
        )
    )
    assert client.is_enabled("planner_v2", workspace_id=WORKSPACE_A) is True
    assert client.is_enabled("planner_v2", workspace_id=WORKSPACE_B) is False
    assert client.is_enabled("planner_v2") is False  # no workspace context


def test_first_matching_rule_wins() -> None:
    client = _client(
        FlagDefinition(
            name="multi",
            default=False,
            rules=[
                FlagRule(workspace_id=WORKSPACE_A, enabled=True),
                FlagRule(workspace_id=WORKSPACE_A, enabled=False),  # ignored
            ],
        )
    )
    assert client.is_enabled("multi", workspace_id=WORKSPACE_A) is True


def test_store_from_env_json_shorthand() -> None:
    store = InMemoryFlagStore.from_env_json('{"a": true, "b": false}')
    assert store.get("a") and store.get("a").default is True
    assert store.get("b") and store.get("b").default is False


def test_store_from_env_json_full_form() -> None:
    store = InMemoryFlagStore.from_env_json('{"x": {"default": true, "description": "demo"}}')
    flag = store.get("x")
    assert flag is not None
    assert flag.default is True
    assert flag.description == "demo"


def test_store_from_env_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        InMemoryFlagStore.from_env_json("[1, 2, 3]")


def test_store_from_env_json_rejects_unsupported_value_type() -> None:
    with pytest.raises(ValueError, match="must be bool or object"):
        InMemoryFlagStore.from_env_json('{"x": "on"}')


def test_get_feature_flag_client_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_feature_flag_client.cache_clear()
    monkeypatch.setenv("AQAO_FEATURE_FLAGS", '{"ga_dashboard": true}')
    client = get_feature_flag_client()
    assert client.is_enabled("ga_dashboard") is True
    get_feature_flag_client.cache_clear()


def test_upsert_replaces_definition() -> None:
    store = InMemoryFlagStore([FlagDefinition(name="z", default=False)])
    store.upsert(FlagDefinition(name="z", default=True))
    flag = store.get("z")
    assert flag is not None
    assert flag.default is True
