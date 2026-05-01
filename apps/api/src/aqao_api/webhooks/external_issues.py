"""Webhook payload handlers for upstream-close sync — Story 3.2.2.

The PRD AC says: "closing the upstream issue reflects in the Agentic QA Orchestrator
defect record within 60 s." That's webhook-driven, not poll. This
module parses Jira and GitHub Issues webhook bodies into the shape
:class:`ExternalIssueService.sync_from_provider` consumes.

Signature verification reuses the Phase-1 GitHub webhook secret for
GitHub events; Jira signing is plumbed but the per-tenant secret
provisioning is deferred per agreed Phase-3 cuts. Tests drive the
handler with parsed payloads directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import ExternalIssue
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.external_issue import ExternalIssueService


class MalformedWebhookPayload(ValueError):  # noqa: N818 - public name; non-Error suffix
    """The webhook body did not contain the fields we expect."""


def process_jira_event(
    *,
    body: dict[str, Any],
    service: ExternalIssueService,
    context: RequestContext,
) -> ExternalIssue | None:
    """Drive a Jira ``jira:issue_updated`` (or similar) event into
    :meth:`ExternalIssueService.sync_from_provider`.

    Returns ``None`` (and swallows :class:`ResourceNotFoundError`) when
    the issue isn't linked — Jira projects connected to many tools fan
    events out broadly, and we shouldn't crash on traffic we don't own.
    """
    issue = body.get("issue")
    if not isinstance(issue, dict):
        raise MalformedWebhookPayload("missing 'issue' object")
    issue_key = issue.get("key")
    if not isinstance(issue_key, str):
        raise MalformedWebhookPayload("issue.key missing or not a string")

    fields = issue.get("fields", {})
    status = (
        fields.get("status", {}).get("statusCategory", {}).get("key", "")
        if isinstance(fields, dict)
        else ""
    )
    closed_at = _parse_iso(fields.get("resolutiondate")) if isinstance(fields, dict) else None

    try:
        return service.sync_from_provider(
            provider="jira",
            issue_key=issue_key,
            provider_status=status,
            closed_at=closed_at,
            raw=body,
            context=context,
        )
    except ResourceNotFoundError:
        return None


def process_github_issues_event(
    *,
    body: dict[str, Any],
    service: ExternalIssueService,
    context: RequestContext,
) -> ExternalIssue | None:
    """Drive a GitHub ``issues`` event (action=opened|closed|reopened)
    into :meth:`ExternalIssueService.sync_from_provider`."""
    issue = body.get("issue")
    if not isinstance(issue, dict):
        raise MalformedWebhookPayload("missing 'issue' object")
    number = issue.get("number")
    if not isinstance(number, int):
        raise MalformedWebhookPayload("issue.number missing or not an int")
    state = issue.get("state")
    if not isinstance(state, str):
        raise MalformedWebhookPayload("issue.state missing or not a string")
    closed_at = _parse_iso(issue.get("closed_at"))

    try:
        return service.sync_from_provider(
            provider="github",
            issue_key=str(number),
            provider_status=state,
            closed_at=closed_at,
            raw=body,
            context=context,
        )
    except ResourceNotFoundError:
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


__all__ = [
    "MalformedWebhookPayload",
    "process_github_issues_event",
    "process_jira_event",
]
