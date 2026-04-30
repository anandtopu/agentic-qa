"""Unit tests for external issue tracking — Stories 3.2.1 / 3.2.2.

Covers:

* Stub clients produce monotonic issue keys and round-trip status.
* Templated body renders the defect into Jira / GitHub Markdown.
* :class:`ExternalIssueService.create_or_reuse` opens a new issue on
  first call and reuses the same link on a second call within the
  dedup window (PRD AC: "deduplicated within 24 h window").
* The Jira webhook handler routes a status flip to ``CLOSED`` end-to-
  end (PRD AC: "closing the upstream issue reflects in the QAForge
  defect record within 60 s" — the time bound is operational; the
  correctness bound is the sync producing the right ``IssueStatus``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    AuditEvent,
    ExternalIssue,
    IssueStatus,
)
from qaforge_api.integrations.external_issues import (
    DEFAULT_GITHUB_TEMPLATE,
    DEFAULT_JIRA_TEMPLATE,
    ExternalIssueError,
    IssueDraft,
    IssueLineAnchor,
    StubGitHubIssuesClient,
    StubJiraClient,
    render_issue_body,
)
from qaforge_api.services.errors import ResourceNotFoundError
from qaforge_api.services.external_issue import ExternalIssueService
from qaforge_api.webhooks.external_issues import (
    MalformedWebhookPayload,
    process_github_issues_event,
    process_jira_event,
)

# ---------------------------------------------------------------- stub session


class _StubSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self._store: dict[tuple[type, UUID], Any] = {}
        self.flushed = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._store[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)

    def get(self, cls: type, ident: UUID) -> Any | None:
        return self._store.get((cls, ident))

    def scalars(self, stmt: Any) -> Any:
        from sqlalchemy.sql import operators

        rows = [r for (cls, _), r in self._store.items() if cls is ExternalIssue]
        for crit in stmt.whereclause.get_children() if stmt.whereclause is not None else []:
            if not (hasattr(crit, "left") and hasattr(crit, "right")):
                continue
            col = getattr(crit.left, "key", None)
            value = getattr(crit.right, "value", None)
            if col is None:
                continue
            if crit.operator is operators.eq:
                rows = [r for r in rows if getattr(r, col) == value]
            elif crit.operator is operators.ge:
                rows = [r for r in rows if getattr(r, col) >= value]
        return _ScalarResult(rows)


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_WORKSPACE = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def context() -> RequestContext:
    return RequestContext(tenant_id=_TENANT, user_id=_USER, correlation_id="trace-1")


@pytest.fixture
def service(session: _StubSession) -> ExternalIssueService:
    return ExternalIssueService(session)  # type: ignore[arg-type]


def _draft(
    *,
    project_key: str = "PROJ",
    title: str = "[QAForge] Login broken",
    body: str = "Body",
) -> IssueDraft:
    return IssueDraft(project_key=project_key, title=title, body_markdown=body)


def _audit_actions(session: _StubSession) -> list[str]:
    return [a.action for a in session.added if isinstance(a, AuditEvent)]


# ---------------------------------------------------------------- stub clients


def test_stub_jira_creates_monotonic_keys() -> None:
    client = StubJiraClient()
    a = client.create(_draft(project_key="QA"))
    b = client.create(_draft(project_key="QA"))
    c = client.create(_draft(project_key="OTHER"))
    assert a.issue_key == "QA-1"
    assert b.issue_key == "QA-2"
    assert c.issue_key == "OTHER-1"
    assert a.issue_url.endswith("/browse/QA-1")


def test_stub_jira_fetch_round_trips_status() -> None:
    client = StubJiraClient()
    created = client.create(_draft(project_key="QA"))
    snap = client.fetch("QA", created.issue_key)
    assert snap.issue_key == created.issue_key
    assert snap.status == "new"
    client.set_status(created.issue_key, status="Done", status_category="done")
    snap2 = client.fetch("QA", created.issue_key)
    assert snap2.status == "done"
    assert snap2.closed_at is not None


def test_stub_jira_fetch_unknown_raises() -> None:
    with pytest.raises(ExternalIssueError):
        StubJiraClient().fetch("QA", "QA-9999")


def test_stub_github_creates_with_owner_repo_url() -> None:
    client = StubGitHubIssuesClient()
    created = client.create(_draft(project_key="acme/payments"))
    assert created.issue_key == "1"
    assert "/acme/payments/issues/1" in created.issue_url


def test_stub_github_review_comment_records_anchor() -> None:
    client = StubGitHubIssuesClient()
    client.add_pr_review_comment(
        project_key="acme/payments",
        pull_number=42,
        body="**Test failure here**",
        anchor=IssueLineAnchor(file_path="src/login.ts", line=88, commit_sha="deadbeef"),
    )
    assert len(client.review_comments) == 1
    rc = client.review_comments[0]
    assert rc.file_path == "src/login.ts"
    assert rc.line == 88
    assert rc.pull_number == 42


# ---------------------------------------------------------------- template


def test_default_jira_template_renders_with_strict_undefined() -> None:
    body = render_issue_body(
        DEFAULT_JIRA_TEMPLATE,
        signal_id="sig-1",
        test_name="test_login",
        category="product_defect",
        confidence="0.85",
        test_run_id="tr-1",
        reasoning="The login button stopped responding to clicks.",
        suggested_fix="Verify the click handler binding.",
        error_message="TimeoutError: button not interactive",
        labels=["regression", "login"],
    )
    assert "test_login" in body
    assert "product_defect" in body
    assert "QAForge correlation: sig-1" in body
    assert "Verify the click handler" in body


def test_github_template_renders_line_anchor_when_present() -> None:
    body = render_issue_body(
        DEFAULT_GITHUB_TEMPLATE,
        signal_id="sig-2",
        test_name=None,
        category="product_defect",
        confidence="0.9",
        test_run_id="tr-2",
        reasoning="500 from /api/login",
        suggested_fix=None,
        error_message=None,
        labels=[],
        line_anchor=IssueLineAnchor(file_path="src/api/login.py", line=42),
    )
    assert "src/api/login.py:42" in body


def test_template_strict_undefined_raises_on_missing_var() -> None:
    from jinja2 import UndefinedError

    with pytest.raises(UndefinedError):
        render_issue_body(DEFAULT_JIRA_TEMPLATE)  # missing every variable


# ---------------------------------------------------------------- service


def test_create_or_reuse_opens_a_new_issue_on_first_call(
    service: ExternalIssueService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    client = StubJiraClient()
    result = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    )
    assert result.deduped is False
    assert result.link.issue_key == "QA-1"
    assert result.link.status == IssueStatus.OPEN.value
    assert "external_issue.create" in _audit_actions(session)


def test_create_or_reuse_dedupes_within_window(
    service: ExternalIssueService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    """PRD AC: deduplicated within 24h window. Second call returns
    the same link with deduped=True and does NOT call client.create."""
    client = StubJiraClient()
    moment = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    first = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
        now=moment,
    )
    later = moment + timedelta(hours=23)
    second = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
        now=later,
    )
    assert second.deduped is True
    assert second.link.id == first.link.id
    # Stub only has one issue — second call did not create another.
    assert len(client.issues) == 1
    assert "external_issue.deduped" in _audit_actions(session)


def test_create_or_reuse_files_again_after_window_expires(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    client = StubJiraClient()
    moment = datetime(2026, 5, 1, tzinfo=UTC)
    service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
        now=moment,
    )
    much_later = moment + timedelta(hours=25)
    second = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
        now=much_later,
    )
    assert second.deduped is False
    assert len(client.issues) == 2


def test_dedup_is_per_workspace_and_per_signal(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    """Different signal -> different issue. Different workspace ->
    different issue. Otherwise dedup would suppress legitimate filings."""
    client = StubJiraClient()
    other_workspace = uuid.uuid4()

    service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    )
    # Different signal in same workspace -> new issue.
    service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-2",
        draft=_draft(project_key="QA"),
        context=context,
    )
    # Same signal in different workspace -> new issue.
    service.create_or_reuse(
        client=client,
        workspace_id=other_workspace,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    )
    assert len(client.issues) == 3


def test_sync_from_provider_maps_jira_done_to_closed(
    service: ExternalIssueService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    """End-to-end: open via service, flip status, drive sync."""
    client = StubJiraClient()
    result = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    )
    assert result.link.status == IssueStatus.OPEN.value

    closed_at = datetime.now(UTC)
    synced = service.sync_from_provider(
        provider="jira",
        issue_key=result.link.issue_key,
        provider_status="done",
        closed_at=closed_at,
        context=context,
    )
    assert synced.status == IssueStatus.CLOSED.value
    assert synced.closed_at == closed_at
    assert synced.last_synced_at is not None
    assert "external_issue.sync" in _audit_actions(session)


def test_sync_from_provider_unknown_status_falls_back_to_open(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    """A workspace with a custom Jira workflow can produce status
    categories we haven't mapped — fall back to OPEN rather than
    silently closing."""
    client = StubJiraClient()
    link = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    ).link
    synced = service.sync_from_provider(
        provider="jira",
        issue_key=link.issue_key,
        provider_status="custom-mystery-state",
        closed_at=None,
        context=context,
    )
    assert synced.status == IssueStatus.OPEN.value


def test_sync_from_provider_for_unknown_link_raises(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    with pytest.raises(ResourceNotFoundError):
        service.sync_from_provider(
            provider="jira",
            issue_key="NOPE-1",
            provider_status="done",
            closed_at=None,
            context=context,
        )


# ---------------------------------------------------------------- webhook handlers


def test_jira_webhook_routes_close_through_to_sync(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    """AC: closing the upstream issue reflects in the QAForge defect
    record. The webhook handler is the seam — give it a Jira payload
    and the link's status flips to CLOSED."""
    client = StubJiraClient()
    link = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="QA"),
        context=context,
    ).link

    body = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": link.issue_key,
            "fields": {
                "status": {
                    "statusCategory": {"key": "done"},
                },
                "resolutiondate": "2026-05-01T12:00:00.000+0000",
            },
        },
    }
    result = process_jira_event(body=body, service=service, context=context)
    assert result is not None
    assert result.status == IssueStatus.CLOSED.value
    assert result.closed_at is not None


def test_github_webhook_closes_link_on_issue_close(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    client = StubGitHubIssuesClient()
    link = service.create_or_reuse(
        client=client,
        workspace_id=_WORKSPACE,
        signal_id="sig-1",
        draft=_draft(project_key="acme/payments"),
        context=context,
    ).link

    body = {
        "action": "closed",
        "issue": {
            "number": int(link.issue_key),
            "state": "closed",
            "closed_at": "2026-05-01T12:00:00Z",
        },
        "repository": {"full_name": "acme/payments"},
    }
    result = process_github_issues_event(body=body, service=service, context=context)
    assert result is not None
    assert result.status == IssueStatus.CLOSED.value


def test_jira_webhook_for_unlinked_issue_returns_none(
    service: ExternalIssueService,
    context: RequestContext,
) -> None:
    """Jira projects are connected to many tools; we shouldn't crash
    on traffic for an issue we don't own."""
    body = {
        "issue": {
            "key": "STRANGER-1",
            "fields": {"status": {"statusCategory": {"key": "done"}}},
        }
    }
    assert process_jira_event(body=body, service=service, context=context) is None


def test_jira_webhook_with_malformed_body_raises() -> None:
    fake_service = object()  # never reached
    with pytest.raises(MalformedWebhookPayload):
        process_jira_event(
            body={"no_issue_field": True},
            service=fake_service,  # type: ignore[arg-type]
            context=RequestContext(tenant_id=_TENANT, user_id=None, correlation_id=None),
        )


def test_github_webhook_with_malformed_body_raises() -> None:
    fake_service = object()
    with pytest.raises(MalformedWebhookPayload):
        process_github_issues_event(
            body={"issue": {"number": "not-an-int", "state": "closed"}},
            service=fake_service,  # type: ignore[arg-type]
            context=RequestContext(tenant_id=_TENANT, user_id=None, correlation_id=None),
        )
