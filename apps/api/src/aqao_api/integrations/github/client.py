"""GitHub client Protocol + DI factory."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import structlog
from pydantic import BaseModel

from aqao_api.config import get_settings


class GitHubError(Exception):
    """Raised on a non-recoverable failure talking to GitHub."""


class InstallationInfo(BaseModel):
    """Subset of the ``/app/installations/{id}`` response we depend on."""

    id: int
    account_login: str
    account_type: str
    suspended: bool = False


class RepositoryInfo(BaseModel):
    """Subset of the ``/repos/{owner}/{repo}`` response we depend on."""

    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool
    html_url: str


class GitHubClient(Protocol):
    """Methods the Repository service needs from the GitHub API."""

    async def get_installation(self, installation_id: int) -> InstallationInfo: ...

    async def get_repository(self, installation_id: int, full_name: str) -> RepositoryInfo: ...

    async def revoke_installation(self, installation_id: int) -> None:
        """Best-effort revoke. Implementations should not raise on 404."""


@lru_cache(maxsize=1)
def get_github_client() -> GitHubClient:
    """Return a real client when credentials exist, else a stub.

    The stub is safe in dev: it accepts any installation id and returns
    deterministic placeholder data. Production deployments must set
    ``AQAO_GITHUB_APP_ID`` and ``AQAO_GITHUB_APP_PRIVATE_KEY_PATH``;
    the API will use the HTTP client automatically.
    """
    settings = get_settings()
    log = structlog.get_logger("aqao_api.integrations.github")

    if settings.github_app_id and settings.github_app_private_key_path:
        from aqao_api.integrations.github.http_client import HttpGitHubClient

        return HttpGitHubClient(
            app_id=settings.github_app_id,
            private_key_path=settings.github_app_private_key_path,
        )

    log.warning(
        "github.using_stub_client",
        reason="AQAO_GITHUB_APP_ID or private key path not configured",
    )
    from aqao_api.integrations.github.stub_client import StubGitHubClient

    return StubGitHubClient()


def reset_github_client_cache() -> None:
    """Test helper — call after monkeypatching settings."""
    get_github_client.cache_clear()
