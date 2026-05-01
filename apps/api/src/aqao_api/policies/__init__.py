"""Agent policy schema (PRD §10.3) and YAML loader.

The policy is the contract every agent operates under: what's allowed,
what requires human approval, and the per-run cost / runtime caps the
Policy Guard enforces. Keeping this in its own module means agents and
the eval harness can validate policies without importing the API layer.
"""

from aqao_api.policies.errors import PolicyParseError, PolicyValidationError
from aqao_api.policies.loader import load_policy_yaml
from aqao_api.policies.schema import (
    DEFAULT_POLICY_YAML,
    AgentPolicy,
    ApprovalGate,
)

__all__ = [
    "DEFAULT_POLICY_YAML",
    "AgentPolicy",
    "ApprovalGate",
    "PolicyParseError",
    "PolicyValidationError",
    "load_policy_yaml",
]
