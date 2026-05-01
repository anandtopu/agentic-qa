"""GitHub App integration for Story 1.1.2.

Public surface:

* :class:`GitHubClient` — the Protocol agents and services depend on.
* :class:`InstallationInfo`, :class:`RepositoryInfo` — typed payloads.
* :class:`GitHubError` — raised on transport failures so callers can
  decide whether to fall back gracefully.
* :func:`get_github_client` — FastAPI dependency that returns a real
  HTTP client when ``AQAO_GITHUB_APP_ID`` is configured, otherwise
  a stub that's safe to use locally.
"""

from aqao_api.integrations.github.client import (
    GitHubClient,
    GitHubError,
    InstallationInfo,
    RepositoryInfo,
    get_github_client,
)
from aqao_api.integrations.github.http_client import HttpGitHubClient
from aqao_api.integrations.github.stub_client import StubGitHubClient

__all__ = [
    "GitHubClient",
    "GitHubError",
    "HttpGitHubClient",
    "InstallationInfo",
    "RepositoryInfo",
    "StubGitHubClient",
    "get_github_client",
]
