"""Unit tests for prompt A/B experiments — Story 3.4.2.

Verifies:

* Variant weights must sum to ~1.0; duplicate names rejected.
* Assignment is **deterministic** for the same (experiment_id, key).
* Traffic split converges on the configured weights over many keys.
* An inactive experiment falls back to the registry's latest /
  configured fallback, and surfaces the reason in the assignment.
* A variant pointing at a missing version falls back gracefully.
"""

from __future__ import annotations

import statistics
import uuid
from collections import Counter

import pytest

from qaforge_agents.prompts import (
    ExperimentSelector,
    PromptExperiment,
    PromptRegistry,
    PromptVariant,
    PromptVersion,
    UnknownPromptVersion,
)


def _registry() -> PromptRegistry:
    return PromptRegistry.of(
        agent="planner",
        versions=[
            PromptVersion(agent="planner", version="1.0.0", system="A"),
            PromptVersion(agent="planner", version="1.1.0", system="B"),
            PromptVersion(agent="planner", version="2.0.0", system="C"),
        ],
    )


def test_experiment_rejects_zero_variants() -> None:
    with pytest.raises(ValueError, match="at least one variant"):
        PromptExperiment(id="exp-1", agent="planner", variants=())


def test_experiment_rejects_duplicate_variant_names() -> None:
    with pytest.raises(ValueError, match="duplicate variant names"):
        PromptExperiment(
            id="exp-1",
            agent="planner",
            variants=(
                PromptVariant(name="control", version="1.0.0", weight=0.5),
                PromptVariant(name="control", version="1.1.0", weight=0.5),
            ),
        )


def test_experiment_rejects_weights_not_summing_to_one() -> None:
    with pytest.raises(ValueError, match="weights must sum"):
        PromptExperiment(
            id="exp-1",
            agent="planner",
            variants=(
                PromptVariant(name="control", version="1.0.0", weight=0.5),
                PromptVariant(name="treatment", version="1.1.0", weight=0.3),
            ),
        )


def test_assignment_is_deterministic_for_same_key() -> None:
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-42",
        agent="planner",
        variants=(
            PromptVariant(name="control", version="1.0.0", weight=0.5),
            PromptVariant(name="treatment", version="1.1.0", weight=0.5),
        ),
    )
    key = uuid.UUID("11111111-1111-1111-1111-111111111111")
    a = selector.select(exp, assignment_key=key)
    b = selector.select(exp, assignment_key=key)
    assert a.variant_name == b.variant_name
    assert a.version.version == b.version.version


def test_traffic_split_converges_to_configured_weights() -> None:
    """Sample 5000 random workspace ids; assignment frequencies should
    be within 5 percentage points of the configured weights."""
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-traffic",
        agent="planner",
        variants=(
            PromptVariant(name="control", version="1.0.0", weight=0.7),
            PromptVariant(name="treatment", version="1.1.0", weight=0.3),
        ),
    )
    counts: Counter[str] = Counter()
    n = 5000
    for _ in range(n):
        assignment = selector.select(exp, assignment_key=uuid.uuid4())
        counts[assignment.variant_name] += 1
    control_share = counts["control"] / n
    treatment_share = counts["treatment"] / n
    assert abs(control_share - 0.70) < 0.05, control_share
    assert abs(treatment_share - 0.30) < 0.05, treatment_share


def test_inactive_experiment_falls_back_to_registry_latest() -> None:
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-off",
        agent="planner",
        active=False,
        variants=(PromptVariant(name="control", version="1.0.0", weight=1.0),),
    )
    a = selector.select(exp, assignment_key="anything")
    assert a.version.version == "2.0.0"  # registry.latest()
    assert a.variant_name == "_fallback:inactive"


def test_inactive_experiment_falls_back_to_configured_pin() -> None:
    """When an explicit fallback is set, the selector returns it
    instead of registry.latest() — matches a workspace that has a
    pin overriding 'track latest'."""
    selector = ExperimentSelector(registry=_registry(), fallback_version="1.0.0")
    exp = PromptExperiment(
        id="exp-off",
        agent="planner",
        active=False,
        variants=(PromptVariant(name="control", version="1.0.0", weight=1.0),),
    )
    a = selector.select(exp, assignment_key="x")
    assert a.version.version == "1.0.0"


def test_selector_rejects_unknown_fallback_version() -> None:
    with pytest.raises(UnknownPromptVersion):
        ExperimentSelector(registry=_registry(), fallback_version="9.9.9")


def test_variant_pointing_at_missing_version_falls_back_with_reason() -> None:
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-missing",
        agent="planner",
        variants=(PromptVariant(name="ghost", version="9.9.9", weight=1.0),),
    )
    a = selector.select(exp, assignment_key="key")
    assert a.variant_name == "_fallback:missing:9.9.9"
    assert a.version.version == "2.0.0"


def test_experiment_agent_must_match_registry_agent() -> None:
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-mismatch",
        agent="api_tester",  # wrong agent
        variants=(PromptVariant(name="control", version="1.0.0", weight=1.0),),
    )
    with pytest.raises(ValueError, match="planner"):
        selector.select(exp, assignment_key="x")


def test_assignment_distribution_uses_full_64bit_bucket() -> None:
    """Sanity check that small key changes can produce different
    variants — a too-narrow hash would cluster assignments."""
    selector = ExperimentSelector(registry=_registry())
    exp = PromptExperiment(
        id="exp-spread",
        agent="planner",
        variants=(
            PromptVariant(name="a", version="1.0.0", weight=0.5),
            PromptVariant(name="b", version="1.1.0", weight=0.5),
        ),
    )
    seen = {selector.select(exp, assignment_key=f"key-{i}").variant_name for i in range(200)}
    assert seen == {"a", "b"}
    # Distribution should be roughly even.
    counts = Counter(
        selector.select(exp, assignment_key=f"key-{i}").variant_name for i in range(1000)
    )
    pct_a = counts["a"] / 1000
    assert abs(pct_a - 0.5) < 0.08, statistics.fmean([pct_a])
