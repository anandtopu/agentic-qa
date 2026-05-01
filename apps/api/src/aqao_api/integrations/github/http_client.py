"""Real GitHub App HTTP client.

Authentication flow:

1. The App's RS256 private key signs a short-lived JWT (iss = app id).
2. We exchange that JWT for an installation token at
   ``POST /app/installations/{id}/access_tokens``.
3. Repository reads then use the installation token as ``Bearer``.

Phase 1 ships the wiring; the JWT signing path is exercised once
``AQAO_GITHUB_APP_ID`` and ``AQAO_GITHUB_APP_PRIVATE_KEY_PATH`` are
set. Until then the factory in ``client.py`` returns the stub.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import structlog

from aqao_api.integrations.github.client import (
    GitHubError,
    InstallationInfo,
    RepositoryInfo,
)

_API_BASE = "https://api.github.com"
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_TOKEN_TTL_SECONDS = 540  # GitHub installation tokens last 1h; refresh under that


class HttpGitHubClient:
    """Production GitHub App client. Lazy: no token until first call."""

    def __init__(
        self,
        *,
        app_id: str,
        private_key_path: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = app_id
        self._private_key_path = Path(private_key_path)
        self._http = http_client or httpx.AsyncClient(base_url=_API_BASE, timeout=_DEFAULT_TIMEOUT)
        self._installation_tokens: dict[int, tuple[str, float]] = {}
        self._log = structlog.get_logger("aqao_api.integrations.github.http")

    async def get_installation(self, installation_id: int) -> InstallationInfo:
        payload = await self._app_request("GET", f"/app/installations/{installation_id}")
        raw_account = payload.get("account")
        account: dict[str, object] = raw_account if isinstance(raw_account, dict) else {}
        raw_id = payload.get("id")
        return InstallationInfo(
            id=int(raw_id) if isinstance(raw_id, (int, str)) else 0,
            account_login=str(account.get("login", "")),
            account_type=str(account.get("type", "Organization")),
            suspended=bool(payload.get("suspended_at")),
        )

    async def get_repository(self, installation_id: int, full_name: str) -> RepositoryInfo:
        token = await self._installation_token(installation_id)
        response = await self._http.get(
            f"/repos/{full_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if response.status_code == 404:
            raise GitHubError(f"repository {full_name} not visible to installation")
        if response.status_code >= 400:
            raise GitHubError(f"github GET /repos/{full_name} failed: {response.status_code}")
        body = response.json()
        owner = body.get("owner") or {}
        return RepositoryInfo(
            id=int(body["id"]),
            owner=str(owner.get("login", "")),
            name=str(body["name"]),
            full_name=str(body["full_name"]),
            default_branch=str(body.get("default_branch", "main")),
            private=bool(body.get("private", False)),
            html_url=str(body.get("html_url", f"https://github.com/{full_name}")),
        )

    async def revoke_installation(self, installation_id: int) -> None:
        try:
            await self._app_request("DELETE", f"/app/installations/{installation_id}")
        except GitHubError as err:
            self._log.warning(
                "github.revoke_failed",
                installation_id=installation_id,
                error=str(err),
            )

    # --- private ---------------------------------------------------------------

    async def _app_request(self, method: str, path: str) -> dict[str, object]:
        jwt_token = self._build_app_jwt()
        response = await self._http.request(
            method,
            path,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if response.status_code == 204:
            return {}
        if response.status_code >= 400:
            raise GitHubError(f"github {method} {path} failed: {response.status_code}")
        return dict(response.json())

    async def _installation_token(self, installation_id: int) -> str:
        cached = self._installation_tokens.get(installation_id)
        now = time.time()
        if cached is not None and cached[1] > now:
            return cached[0]
        payload = await self._app_request(
            "POST", f"/app/installations/{installation_id}/access_tokens"
        )
        token = str(payload["token"])
        self._installation_tokens[installation_id] = (token, now + _TOKEN_TTL_SECONDS)
        return token

    def _build_app_jwt(self) -> str:
        try:
            import jwt
        except ImportError as exc:  # pragma: no cover - hard error at first call
            raise GitHubError(
                "PyJWT is required for the HTTP GitHub client; add it to apps/api deps"
            ) from exc

        if not self._private_key_path.is_file():
            raise GitHubError(f"GitHub App private key not found at {self._private_key_path}")

        now = int(time.time())
        claims = {
            "iat": now - 30,
            "exp": now + 540,
            "iss": self._app_id,
        }
        private_key = self._private_key_path.read_text()
        token: str = jwt.encode(claims, private_key, algorithm="RS256")
        return token
