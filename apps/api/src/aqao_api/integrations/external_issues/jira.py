"""Jira integration — Story 3.2.1.

``StubJiraClient`` is the in-process implementation used by tests +
local dev (no Jira tenant required). ``JiraHttpClient`` talks to the
Jira REST API v3 over httpx; per agreed Phase-3 cuts, the integration
test against a real Jira tenant is deferred until credentials are
provisioned — the stub is the contract this module commits to.
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
    IssueSnapshot,
)

_JIRA_TERMINAL_CATEGORIES = frozenset({"done", "closed", "resolved"})


@dataclass(slots=True)
class StubJiraClient:
    """In-memory Jira client.

    Issue keys are produced as ``{PROJECT}-{n}`` where ``n`` is a
    per-project monotonically-increasing counter. Tests can inspect
    ``issues`` directly to assert on the body, or call
    :meth:`set_status` to simulate the upstream-close webhook.
    """

    base_url: str = "https://aqao.test.atlassian.net"
    provider: str = "jira"
    issues: dict[str, dict[str, Any]] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create(self, draft: IssueDraft) -> CreatedIssue:
        with self._lock:
            self._counters[draft.project_key] = self._counters.get(draft.project_key, 0) + 1
            n = self._counters[draft.project_key]
        key = f"{draft.project_key}-{n}"
        url = f"{self.base_url}/browse/{key}"
        record = {
            "key": key,
            "url": url,
            "title": draft.title,
            "body": draft.body_markdown,
            "labels": list(draft.labels),
            "priority": draft.priority,
            "status": "To Do",
            "status_category": "new",
            "created_at": datetime.now(UTC),
            "closed_at": None,
        }
        self.issues[key] = record
        return CreatedIssue(issue_key=key, issue_url=url, raw=dict(record))

    def fetch(self, project_key: str, issue_key: str) -> IssueSnapshot:
        record = self.issues.get(issue_key)
        if record is None or not issue_key.startswith(project_key + "-"):
            raise ExternalIssueError(f"Jira issue {issue_key!r} not found in stub")
        return IssueSnapshot(
            issue_key=issue_key,
            status=record["status_category"],
            closed_at=record["closed_at"],
            raw=dict(record),
        )

    # ----------------------- test helpers ---------------------------------

    def set_status(
        self,
        issue_key: str,
        *,
        status: str,
        status_category: str,
        closed_at: datetime | None = None,
    ) -> None:
        record = self.issues.get(issue_key)
        if record is None:
            raise ExternalIssueError(f"unknown stub issue {issue_key!r}")
        record["status"] = status
        record["status_category"] = status_category
        if status_category in _JIRA_TERMINAL_CATEGORIES:
            record["closed_at"] = closed_at or datetime.now(UTC)
        else:
            record["closed_at"] = None


@dataclass(slots=True)
class JiraHttpClient:
    """Production Jira REST API v3 client.

    Construction takes the workspace's site URL + auth headers; per-call
    the caller passes the project key. ``create()`` POSTs to
    ``/rest/api/3/issue`` and reads ``{"key", "self"}``; ``fetch()``
    GETs ``/rest/api/3/issue/{issue_key}`` and reads
    ``fields.status.statusCategory.key``.
    """

    base_url: str
    auth_header: str  # e.g. "Basic base64(email:token)"
    timeout_seconds: float = 10.0
    provider: str = "jira"

    def create(self, draft: IssueDraft) -> CreatedIssue:
        payload = {
            "fields": {
                "project": {"key": draft.project_key},
                "summary": draft.title,
                "description": _adf_paragraph(draft.body_markdown),
                "issuetype": {"name": "Bug"},
                "labels": list(draft.labels),
            }
        }
        if draft.priority is not None:
            payload["fields"]["priority"] = {"name": draft.priority}

        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/rest/api/3/issue",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ExternalIssueError(f"Jira create transport error: {exc}") from exc
        if response.status_code >= 400:
            raise ExternalIssueError(f"Jira create failed: {response.status_code} {response.text}")
        body = response.json()
        key = body["key"]
        return CreatedIssue(
            issue_key=key,
            issue_url=f"{self.base_url.rstrip('/')}/browse/{key}",
            raw=body,
        )

    def fetch(self, project_key: str, issue_key: str) -> IssueSnapshot:
        try:
            response = httpx.get(
                f"{self.base_url.rstrip('/')}/rest/api/3/issue/{issue_key}",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ExternalIssueError(f"Jira fetch transport error: {exc}") from exc
        if response.status_code == 404:
            raise ExternalIssueError(f"Jira issue {issue_key} not found")
        if response.status_code >= 400:
            raise ExternalIssueError(f"Jira fetch failed: {response.status_code} {response.text}")
        body = response.json()
        category = body.get("fields", {}).get("status", {}).get("statusCategory", {}).get("key", "")
        closed_at: datetime | None = None
        resolved_raw = body.get("fields", {}).get("resolutiondate")
        if resolved_raw:
            closed_at = datetime.fromisoformat(resolved_raw.replace("Z", "+00:00"))
        return IssueSnapshot(
            issue_key=issue_key,
            status=category,
            closed_at=closed_at,
            raw=body,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.auth_header,
        }


def _adf_paragraph(text: str) -> dict[str, Any]:
    """Wrap a Markdown body in Atlassian Document Format. Phase-3
    ships a minimal wrapper — multi-block ADF rendering is out of
    scope. Most Jira instances render the resulting paragraph as
    preformatted text, which is good enough for a defect body."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


__all__ = ["JiraHttpClient", "StubJiraClient"]
