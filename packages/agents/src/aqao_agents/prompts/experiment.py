"""Prompt A/B experiments — Story 3.4.2.

A :class:`PromptExperiment` carries two or more :class:`PromptVariant`
entries with traffic weights summing to 1.0. Assignment is **deterministic**
based on a hash of the experiment id + assignment key (typically
``workspace_id`` or ``test_run_id``), so the same caller always sees the
same variant for the lifetime of the experiment.

Promotion of a winning variant is a separate step — the API layer
records the decision in the audit log and updates the workspace's
prompt pin via the same service that handles ungated pins.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from aqao_agents.prompts.registry import (
    PromptRegistry,
    PromptVersion,
    UnknownPromptVersion,
)


@dataclass(slots=True, frozen=True)
class PromptVariant:
    """One arm of an A/B experiment."""

    name: str  # e.g. "control" or "treatment"
    version: str  # must exist in the agent's PromptRegistry
    weight: float  # 0..1; weights across variants sum to 1.0


@dataclass(slots=True, frozen=True)
class PromptExperiment:
    """Configuration for a running prompt experiment.

    The experiment is uniquely identified by ``id`` so deterministic
    assignment is stable even if two experiments happen to use the
    same agent. ``active=False`` means the selector will fall back to
    the registry's latest (or to a static pin if the caller passes
    one), so disabling an experiment is a one-flag operation.
    """

    id: str
    agent: str
    variants: tuple[PromptVariant, ...]
    active: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError(f"experiment {self.id!r} must have at least one variant")
        names = [v.name for v in self.variants]
        if len(names) != len(set(names)):
            raise ValueError(f"experiment {self.id!r} has duplicate variant names")
        total = sum(v.weight for v in self.variants)
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"experiment {self.id!r} weights must sum to ~1.0 (got {total:.3f})")
        for v in self.variants:
            if not (0.0 <= v.weight <= 1.0):
                raise ValueError(f"variant {v.name!r} weight must be in [0,1] (got {v.weight})")


@dataclass(slots=True, frozen=True)
class ExperimentAssignment:
    """Result of selecting a variant for one assignment key."""

    experiment_id: str
    variant_name: str
    version: PromptVersion


@dataclass(slots=True)
class ExperimentSelector:
    """Maps ``(experiment, assignment_key) -> ExperimentAssignment``.

    The selector does **not** record the assignment — that's the
    caller's responsibility (typically via usage_records). It only
    decides which variant to use, deterministically, given the
    experiment configuration and a stable assignment key.
    """

    registry: PromptRegistry
    fallback_version: str | None = None

    def __post_init__(self) -> None:
        # Verify referenced versions exist now so the failure surfaces
        # at construction rather than at first traffic.
        if self.fallback_version is not None and not self.registry.has_version(
            self.fallback_version
        ):
            raise UnknownPromptVersion(self.registry.agent, self.fallback_version)

    def select(
        self,
        experiment: PromptExperiment,
        *,
        assignment_key: str | UUID,
    ) -> ExperimentAssignment:
        """Pick a variant for the given assignment key.

        ``assignment_key`` should be stable for the lifetime of the
        decision (e.g. workspace_id, test_run_id). The same key + the
        same experiment id will always produce the same variant.
        """
        if experiment.agent != self.registry.agent:
            raise ValueError(
                f"experiment {experiment.id!r} is for agent "
                f"{experiment.agent!r}, registry is for {self.registry.agent!r}"
            )
        if not experiment.active:
            return self._fallback(experiment_id=experiment.id, reason="inactive")

        key = f"{experiment.id}:{assignment_key}".encode()
        digest = hashlib.sha256(key).digest()
        # Use the first 8 bytes as a uniform float in [0,1).
        bucket = int.from_bytes(digest[:8], "big") / float(1 << 64)

        cumulative = 0.0
        chosen: PromptVariant | None = None
        for variant in experiment.variants:
            cumulative += variant.weight
            if bucket < cumulative:
                chosen = variant
                break
        if chosen is None:
            # Floating-point edge — fall through to the last variant.
            chosen = experiment.variants[-1]

        try:
            version = self.registry.resolve(chosen.version)
        except UnknownPromptVersion:
            return self._fallback(experiment_id=experiment.id, reason=f"missing:{chosen.version}")
        return ExperimentAssignment(
            experiment_id=experiment.id,
            variant_name=chosen.name,
            version=version,
        )

    def _fallback(self, *, experiment_id: str, reason: str) -> ExperimentAssignment:
        version = (
            self.registry.resolve(self.fallback_version)
            if self.fallback_version is not None
            else self.registry.latest()
        )
        return ExperimentAssignment(
            experiment_id=experiment_id,
            variant_name=f"_fallback:{reason}",
            version=version,
        )


__all__ = [
    "ExperimentAssignment",
    "ExperimentSelector",
    "PromptExperiment",
    "PromptVariant",
]
