"""Unit tests for the StubGitHubClient.

The stub backs all integration tests until a real GitHub App is wired
in production. Its behaviour is part of the contract.
"""

from __future__ import annotations

import asyncio

import pytest

from aqao_api.integrations.github.client import GitHubError
from aqao_api.integrations.github.stub_client import StubGitHubClient


def test_get_repository_returns_canned_when_registered() -> None:
    stub = StubGitHubClient()
    stub.register_repository(installation_id=42, full_name="org/payments", default_branch="develop")
    info = asyncio.run(stub.get_repository(42, "org/payments"))
    assert info.full_name == "org/payments"
    assert info.default_branch == "develop"


def test_get_repository_synthesises_when_unregistered() -> None:
    stub = StubGitHubClient()
    info = asyncio.run(stub.get_repository(7, "acme/widgets"))
    assert info.owner == "acme"
    assert info.name == "widgets"
    assert info.default_branch == "main"


def test_get_repository_rejects_invalid_full_name() -> None:
    stub = StubGitHubClient()
    with pytest.raises(GitHubError):
        asyncio.run(stub.get_repository(1, "no-slash"))


def test_revoke_records_call_and_marks_install() -> None:
    stub = StubGitHubClient()
    stub.register_installation(99, account_login="acme")
    asyncio.run(stub.revoke_installation(99))
    assert stub.revoked_installations == [99]
    assert stub.installations[99].revoked is True


def test_revoke_can_be_configured_to_fail() -> None:
    stub = StubGitHubClient(fail_on_revoke=True)
    with pytest.raises(GitHubError):
        asyncio.run(stub.revoke_installation(1))


def test_get_installation_after_revoke_raises() -> None:
    stub = StubGitHubClient()
    stub.register_installation(7)
    asyncio.run(stub.revoke_installation(7))
    with pytest.raises(GitHubError):
        asyncio.run(stub.get_installation(7))
