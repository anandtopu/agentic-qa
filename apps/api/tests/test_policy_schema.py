"""Unit tests for the policy schema + YAML loader.

These run without a database and exercise the Story 1.1.3 AC most
directly: a policy violating the schema yields field-level errors
suitable for a 422 response.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from aqao_api.policies import (
    DEFAULT_POLICY_YAML,
    AgentPolicy,
    PolicyParseError,
    PolicyValidationError,
    load_policy_yaml,
)
from aqao_api.policies.schema import ApprovalGate


def test_default_policy_yaml_round_trips() -> None:
    policy = load_policy_yaml(DEFAULT_POLICY_YAML)
    assert isinstance(policy, AgentPolicy)
    assert policy.allow_write_operations is False
    assert policy.redact_secrets is True
    assert policy.max_cost_usd_per_run == Decimal("5.00")
    assert policy.max_runtime_minutes == 30
    assert ApprovalGate.DESTRUCTIVE_SQL in policy.require_approval_for


def test_loader_accepts_flat_top_level_mapping() -> None:
    yaml_doc = """
    allow_write_operations: true
    redact_secrets: false
    max_cost_usd_per_run: 1.25
    max_runtime_minutes: 5
    require_approval_for:
      - external_ticket_creation
    """
    policy = load_policy_yaml(yaml_doc)
    assert policy.allow_write_operations is True
    assert policy.redact_secrets is False
    assert policy.max_cost_usd_per_run == Decimal("1.25")


def test_loader_rejects_unknown_field_with_field_path() -> None:
    yaml_doc = """
    policy:
      allow_write_operations: false
      mystery_knob: true
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    errors = exc_info.value.errors
    assert any("mystery_knob" in str(e.location) for e in errors)


def test_loader_rejects_negative_max_cost() -> None:
    yaml_doc = """
    policy:
      max_cost_usd_per_run: -1.0
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    locations = [e.location for e in exc_info.value.errors]
    assert ("max_cost_usd_per_run",) in locations


def test_loader_rejects_invalid_approval_gate_enum() -> None:
    yaml_doc = """
    policy:
      require_approval_for:
        - launch_nukes
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    assert any("require_approval_for" in str(e.location) for e in exc_info.value.errors)


def test_loader_rejects_max_runtime_above_one_day() -> None:
    yaml_doc = """
    policy:
      max_runtime_minutes: 9999
    """
    with pytest.raises(PolicyValidationError):
        load_policy_yaml(yaml_doc)


def test_loader_rejects_duplicate_approval_gates() -> None:
    yaml_doc = """
    policy:
      require_approval_for:
        - destructive_sql
        - destructive_sql
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    assert any("duplicate" in e.message.lower() for e in exc_info.value.errors)


def test_retention_overrides_round_trip() -> None:
    yaml_doc = """
    policy:
      retention:
        test_runs: 200
        agent_feedback: 365
    """
    policy = load_policy_yaml(yaml_doc)
    assert policy.retention == {"test_runs": 200, "agent_feedback": 365}


def test_retention_defaults_to_empty_map() -> None:
    policy = load_policy_yaml(DEFAULT_POLICY_YAML)
    assert policy.retention == {}


def test_retention_rejects_non_overridable_class() -> None:
    # audit_events is compliance-locked → not in the overridable set.
    yaml_doc = """
    policy:
      retention:
        audit_events: 100
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    assert any("overridable" in e.message.lower() for e in exc_info.value.errors)


def test_retention_rejects_window_above_max() -> None:
    yaml_doc = """
    policy:
      retention:
        test_runs: 9999
    """
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy_yaml(yaml_doc)
    assert any("365" in e.message for e in exc_info.value.errors)


def test_retention_rejects_non_positive_window() -> None:
    yaml_doc = """
    policy:
      retention:
        test_runs: 0
    """
    with pytest.raises(PolicyValidationError):
        load_policy_yaml(yaml_doc)


def test_loader_raises_parse_error_on_malformed_yaml() -> None:
    with pytest.raises(PolicyParseError):
        load_policy_yaml("policy: [unterminated")


def test_loader_rejects_empty_document() -> None:
    with pytest.raises(PolicyValidationError):
        load_policy_yaml("")


def test_loader_rejects_non_mapping_top_level() -> None:
    with pytest.raises(PolicyValidationError):
        load_policy_yaml("- 1\n- 2\n")
