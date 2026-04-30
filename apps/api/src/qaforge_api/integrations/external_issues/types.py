"""Provider-agnostic types for external trackers — Story 3.2.x.

The :class:`ExternalIssueClient` Protocol is the seam every provider
satisfies. Service code calls ``create()`` to file an issue and
``fetch()`` to read its current state during a webhook-driven
close-sync. Anything richer (transitions, comments) goes through
provider-specific impls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class ExternalIssueError(RuntimeError):
    """Provider call failed — auth, network, validation."""


@dataclass(slots=True, frozen=True)
class IssueLineAnchor:
    """Code-line reference used by the GitHub PR-review-comment path
    (Story 3.2.2). Optional — Jira issues ignore it."""

    file_path: str
    line: int
    commit_sha: str | None = None


@dataclass(slots=True, frozen=True)
class IssueDraft:
    """Caller-side description of the issue to file.

    The provider impl renders this into its native shape (Jira ADF,
    GitHub Markdown). ``labels`` is provider-agnostic; ``priority`` is
    a string the provider maps to its own scheme (e.g. Jira "High").
    """

    project_key: str
    title: str
    body_markdown: str
    labels: tuple[str, ...] = ()
    priority: str | None = None
    line_anchor: IssueLineAnchor | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class CreatedIssue:
    """What a provider returns after a successful ``create()`` call."""

    issue_key: str
    issue_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class IssueSnapshot:
    """Current state of an external issue — used by the close-sync
    webhook to update the QAForge defect record."""

    issue_key: str
    status: str  # provider-native; service maps to IssueStatus
    closed_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ExternalIssueClient(Protocol):
    """Surface every provider impl satisfies."""

    provider: str

    def create(self, draft: IssueDraft) -> CreatedIssue: ...

    def fetch(self, project_key: str, issue_key: str) -> IssueSnapshot: ...


__all__ = [
    "CreatedIssue",
    "ExternalIssueClient",
    "ExternalIssueError",
    "IssueDraft",
    "IssueLineAnchor",
    "IssueSnapshot",
]
