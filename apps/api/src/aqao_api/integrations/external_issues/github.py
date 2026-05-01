"""GitHub Issues integration — Story 3.2.2.

``StubGitHubIssuesClient`` is the in-process impl used by tests +
local dev. ``GitHubIssuesHttpClient`` talks to the REST v3 API; per
agreed Phase-3 cuts, the integration test against a real GitHub repo
is deferred until credentials are provisioned.

The PR-review-comment with line anchoring (PRD AC) is a separate
endpoint (``/repos/{owner}/{repo}/pulls/{pull}/comments``) that the
service can opt into when an :class:`IssueLineAnchor` is provided.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from aqao_api.integrations.external_issues.types import (
    CreatedIssue,
    ExternalIssueError,
    IssueDraft,
    IssueLineAnchor,
    IssueSnapshot,
)


@dataclass(slots=True)
class _StubReviewComment:
    pull_number: int
    file_path: str
    line: int
    body: str
    commit_sha: str | None
    created_at: datetime


@dataclass(slots=True)
class StubGitHubIssuesClient:
    """In-memory GitHub Issues client.

    ``project_key`` is the repo slug ``owner/repo``. ``issue_key`` is
    the integer issue number rendered as a string for symmetry with
    the Jira impl.
    """

    base_url: str = "https://github.com"
    provider: str = "github"
    issues: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    review_comments: list[_StubReviewComment] = field(default_factory=list)
    _counters: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create(self, draft: IssueDraft) -> CreatedIssue:
        with self._lock:
            self._counters[draft.project_key] = self._counters.get(draft.project_key, 0) + 1
            n = self._counters[draft.project_key]
        key = str(n)
        url = f"{self.base_url}/{draft.project_key}/issues/{n}"
        record: dict[str, Any] = {
            "number": n,
            "url": url,
            "title": draft.title,
            "body": draft.body_markdown,
            "labels": list(draft.labels),
            "state": "open",
            "created_at": datetime.now(UTC),
            "closed_at": None,
        }
        self.issues[(draft.project_key, key)] = record
        return CreatedIssue(issue_key=key, issue_url=url, raw=dict(record))

    def fetch(self, project_key: str, issue_key: str) -> IssueSnapshot:
        record = self.issues.get((project_key, issue_key))
        if record is None:
            raise ExternalIssueError(f"GitHub issue {project_key}#{issue_key} not found in stub")
        return IssueSnapshot(
            issue_key=issue_key,
            status=record["state"],
            closed_at=record["closed_at"],
            raw=dict(record),
        )

    # ----------------------- PR review comments (Story 3.2.2) ----------

    def add_pr_review_comment(
        self,
        *,
        project_key: str,
        pull_number: int,
        body: str,
        anchor: IssueLineAnchor,
    ) -> _StubReviewComment:
        comment = _StubReviewComment(
            pull_number=pull_number,
            file_path=anchor.file_path,
            line=anchor.line,
            body=body,
            commit_sha=anchor.commit_sha,
            created_at=datetime.now(UTC),
        )
        self.review_comments.append(comment)
        return comment

    # ----------------------- test helpers ------------------------------

    def set_state(
        self,
        *,
        project_key: str,
        issue_key: str,
        state: str,
        closed_at: datetime | None = None,
    ) -> None:
        record = self.issues.get((project_key, issue_key))
        if record is None:
            raise ExternalIssueError(f"unknown stub GitHub issue {project_key}#{issue_key}")
        record["state"] = state
        if state == "closed":
            record["closed_at"] = closed_at or datetime.now(UTC)
        else:
            record["closed_at"] = None


@dataclass(slots=True)
class GitHubIssuesHttpClient:
    """Production GitHub Issues client.

    Auth is a personal-access-token / GitHub App token passed via the
    ``Authorization: Bearer ...`` header.
    """

    base_url: str = "https://api.github.com"
    token: str = ""
    timeout_seconds: float = 10.0
    provider: str = "github"

    def create(self, draft: IssueDraft) -> CreatedIssue:
        owner, _, repo = draft.project_key.partition("/")
        if not owner or not repo:
            raise ExternalIssueError(
                f"GitHub project_key must be 'owner/repo', got {draft.project_key!r}"
            )
        payload = {
            "title": draft.title,
            "body": draft.body_markdown,
            "labels": list(draft.labels),
        }
        try:
            response = httpx.post(
                f"{self.base_url}/repos/{owner}/{repo}/issues",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ExternalIssueError(f"GitHub create transport error: {exc}") from exc
        if response.status_code >= 400:
            raise ExternalIssueError(
                f"GitHub create failed: {response.status_code} {response.text}"
            )
        body = response.json()
        return CreatedIssue(
            issue_key=str(body["number"]),
            issue_url=body["html_url"],
            raw=body,
        )

    def fetch(self, project_key: str, issue_key: str) -> IssueSnapshot:
        owner, _, repo = project_key.partition("/")
        try:
            response = httpx.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_key}",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            raise ExternalIssueError(f"GitHub fetch transport error: {exc}") from exc
        if response.status_code == 404:
            raise ExternalIssueError(f"GitHub issue {project_key}#{issue_key} not found")
        if response.status_code >= 400:
            raise ExternalIssueError(f"GitHub fetch failed: {response.status_code} {response.text}")
        body = response.json()
        closed_at_raw = body.get("closed_at")
        closed_at: datetime | None = None
        if closed_at_raw:
            closed_at = datetime.fromisoformat(closed_at_raw.replace("Z", "+00:00"))
        return IssueSnapshot(
            issue_key=issue_key,
            status=body.get("state", "open"),
            closed_at=closed_at,
            raw=body,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }


__all__ = ["GitHubIssuesHttpClient", "StubGitHubIssuesClient"]
