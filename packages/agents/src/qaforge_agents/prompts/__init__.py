"""Prompt + version registry — Epic 3.4.

Every agent's prompt is versioned with a semver, a changelog, and an
optional eval link (the scorecard URL or path that demonstrates the
version's quality bar). A workspace can pin production traffic to a
specific version; A/B experiments split traffic between two variants
and surface the winner.

Public surface:

* :class:`PromptVersion` — one immutable revision of a prompt.
* :class:`PromptRegistry` — collection of versions for one agent.
* :class:`UnknownPromptVersion` — raised when a pin / experiment
  references a version the registry doesn't know.
* :class:`PromptExperiment` + :class:`ExperimentSelector` — Story 3.4.2
  traffic-split machinery with deterministic assignment.
"""

from qaforge_agents.prompts.experiment import (
    ExperimentAssignment,
    ExperimentSelector,
    PromptExperiment,
    PromptVariant,
)
from qaforge_agents.prompts.registry import (
    PromptRegistry,
    PromptVersion,
    UnknownPromptVersion,
    parse_semver,
)

__all__ = [
    "ExperimentAssignment",
    "ExperimentSelector",
    "PromptExperiment",
    "PromptRegistry",
    "PromptVariant",
    "PromptVersion",
    "UnknownPromptVersion",
    "parse_semver",
]
