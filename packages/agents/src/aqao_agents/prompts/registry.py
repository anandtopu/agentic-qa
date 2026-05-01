"""PromptVersion + PromptRegistry — Story 3.4.1.

Every prompt revision carries a semver, the prompt body itself, a
changelog explaining what changed, and an optional ``eval_link``
pointing at the scorecard or eval run that justifies the version
shipping. The registry orders versions by semver and exposes
``latest()`` plus a ``resolve(version)`` lookup.

The registry is **immutable** — it's built at import time from the
agent's prompt module and treated as the source of truth for what
versions exist. Workspace pins (Story 3.4.1's DB side) and
experiments (Story 3.4.2) only ever *select* an existing version;
they cannot mint a new one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


class UnknownPromptVersion(KeyError):  # noqa: N818 - public name; intentional non-Error suffix
    """A pin / experiment named a version the registry doesn't know."""

    def __init__(self, agent: str, version: str) -> None:
        super().__init__(f"agent {agent!r} has no prompt version {version!r}")
        self.agent = agent
        self.version = version


_SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<pre>[A-Za-z0-9.\-]+))?$"
)


def parse_semver(value: str) -> tuple[int, int, int, str]:
    """Parse a semver string into a sortable 4-tuple.

    Pre-release suffixes sort *before* the corresponding release
    (``1.0.0-rc.1`` < ``1.0.0``) — we encode this by giving release
    versions an empty pre-release tag, which sorts greater than any
    non-empty string under the chosen comparator. Callers should not
    rely on the tuple shape — sort with :func:`parse_semver` as the
    key and otherwise treat the string as opaque.
    """
    match = _SEMVER_RE.match(value)
    if match is None:
        raise ValueError(f"not a semver string: {value!r}")
    pre = match.group("pre") or "~"  # tilde > any printable ASCII
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        pre,
    )


@dataclass(slots=True, frozen=True)
class PromptVersion:
    """One immutable revision of an agent's prompt."""

    agent: str
    version: str
    system: str
    changelog: str = ""
    eval_link: str | None = None
    user_template: str | None = None

    def __post_init__(self) -> None:
        # Validate semver at construction so a typo in a prompt module
        # fails import rather than silently sorting wrong later.
        parse_semver(self.version)


@dataclass(slots=True, frozen=True)
class PromptRegistry:
    """Ordered set of :class:`PromptVersion` for one agent.

    ``versions`` is sorted by semver ascending so ``latest()`` is the
    last element. The registry rejects duplicate versions for the
    same agent at construction.
    """

    agent: str
    versions: tuple[PromptVersion, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, *, agent: str, versions: Iterable[PromptVersion]) -> PromptRegistry:
        seen: set[str] = set()
        ordered: list[PromptVersion] = []
        for v in versions:
            if v.agent != agent:
                raise ValueError(f"version {v.version} is for agent {v.agent!r}, not {agent!r}")
            if v.version in seen:
                raise ValueError(f"duplicate prompt version {v.version!r} for agent {agent!r}")
            seen.add(v.version)
            ordered.append(v)
        ordered.sort(key=lambda x: parse_semver(x.version))
        return cls(agent=agent, versions=tuple(ordered))

    def latest(self) -> PromptVersion:
        if not self.versions:
            raise UnknownPromptVersion(self.agent, "<latest>")
        return self.versions[-1]

    def resolve(self, version: str | None = None) -> PromptVersion:
        """Look up a version by string, falling back to ``latest()`` on ``None``.

        Raises :class:`UnknownPromptVersion` if the requested version
        isn't registered — never silently downgrades to ``latest`` so
        a stale pin in production is loud.
        """
        if version is None:
            return self.latest()
        for v in self.versions:
            if v.version == version:
                return v
        raise UnknownPromptVersion(self.agent, version)

    def has_version(self, version: str) -> bool:
        return any(v.version == version for v in self.versions)


__all__ = [
    "PromptRegistry",
    "PromptVersion",
    "UnknownPromptVersion",
    "parse_semver",
]
