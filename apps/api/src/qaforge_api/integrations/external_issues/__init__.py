"""External issue tracker clients — Stories 3.2.1 / 3.2.2.

Provider-agnostic Protocols + in-memory stubs (test/dev) + production
HTTP impls. The :class:`ExternalIssueService` consumes these via the
:class:`ExternalIssueClient` Protocol so dedup + audit logic doesn't
care which tracker is on the other end.
"""

from qaforge_api.integrations.external_issues.github import (
    GitHubIssuesHttpClient,
    StubGitHubIssuesClient,
)
from qaforge_api.integrations.external_issues.jira import (
    JiraHttpClient,
    StubJiraClient,
)
from qaforge_api.integrations.external_issues.template import (
    DEFAULT_GITHUB_TEMPLATE,
    DEFAULT_JIRA_TEMPLATE,
    render_issue_body,
)
from qaforge_api.integrations.external_issues.types import (
    CreatedIssue,
    ExternalIssueClient,
    ExternalIssueError,
    IssueDraft,
    IssueLineAnchor,
    IssueSnapshot,
)

__all__ = [
    "DEFAULT_GITHUB_TEMPLATE",
    "DEFAULT_JIRA_TEMPLATE",
    "CreatedIssue",
    "ExternalIssueClient",
    "ExternalIssueError",
    "GitHubIssuesHttpClient",
    "IssueDraft",
    "IssueLineAnchor",
    "IssueSnapshot",
    "JiraHttpClient",
    "StubGitHubIssuesClient",
    "StubJiraClient",
    "render_issue_body",
]
