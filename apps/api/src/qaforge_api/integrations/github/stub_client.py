"""In-memory GitHub client for local dev and tests.

Returns deterministic placeholder data based on the inputs so a developer
can exercise the link/unlink flow without a real GitHub App.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qaforge_api.integrations.github.client import (
    GitHubError,
    InstallationInfo,
    RepositoryInfo,
)


@dataclass(slots=True)
class _Installation:
    info: InstallationInfo
    revoked: bool = False


@dataclass(slots=True)
class StubGitHubClient:
    """Pluggable stub.

    By default any (installation_id, full_name) is "valid" — the stub
    fabricates a RepositoryInfo. Tests can pre-register specific
    repositories or installations to control the response shape.
    """

    installations: dict[int, _Installation] = field(default_factory=dict)
    repositories: dict[tuple[int, str], RepositoryInfo] = field(default_factory=dict)
    fail_on_revoke: bool = False
    revoked_installations: list[int] = field(default_factory=list)

    def register_installation(
        self,
        installation_id: int,
        *,
        account_login: str = "stub-org",
        account_type: str = "Organization",
    ) -> None:
        self.installations[installation_id] = _Installation(
            info=InstallationInfo(
                id=installation_id,
                account_login=account_login,
                account_type=account_type,
            )
        )

    def register_repository(
        self,
        installation_id: int,
        full_name: str,
        *,
        repo_id: int = 12345,
        default_branch: str = "main",
        private: bool = False,
    ) -> None:
        owner, _, name = full_name.partition("/")
        self.repositories[(installation_id, full_name)] = RepositoryInfo(
            id=repo_id,
            owner=owner,
            name=name,
            full_name=full_name,
            default_branch=default_branch,
            private=private,
            html_url=f"https://github.com/{full_name}",
        )

    async def get_installation(self, installation_id: int) -> InstallationInfo:
        installation = self.installations.get(installation_id)
        if installation is None:
            return InstallationInfo(
                id=installation_id,
                account_login="stub-org",
                account_type="Organization",
            )
        if installation.revoked:
            raise GitHubError(f"installation {installation_id} is revoked")
        return installation.info

    async def get_repository(self, installation_id: int, full_name: str) -> RepositoryInfo:
        cached = self.repositories.get((installation_id, full_name))
        if cached is not None:
            return cached
        owner, _, name = full_name.partition("/")
        if not owner or not name:
            raise GitHubError(f"invalid full_name: {full_name!r}")
        return RepositoryInfo(
            id=hash((installation_id, full_name)) & 0x7FFFFFFF,
            owner=owner,
            name=name,
            full_name=full_name,
            default_branch="main",
            private=False,
            html_url=f"https://github.com/{full_name}",
        )

    async def revoke_installation(self, installation_id: int) -> None:
        if self.fail_on_revoke:
            raise GitHubError(f"stub configured to fail revoke for {installation_id}")
        self.revoked_installations.append(installation_id)
        if installation_id in self.installations:
            self.installations[installation_id].revoked = True
