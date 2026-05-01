"""Unit tests for repository API schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aqao_api.schemas.repository import RepositoryLinkRequest


def test_link_request_accepts_owner_repo() -> None:
    payload = RepositoryLinkRequest(installation_id=42, full_name="org/payments")
    assert payload.installation_id == 42
    assert payload.full_name == "org/payments"


def test_link_request_rejects_negative_install_id() -> None:
    with pytest.raises(ValidationError):
        RepositoryLinkRequest(installation_id=0, full_name="org/payments")


def test_link_request_rejects_non_owner_repo_format() -> None:
    for bad in ("payments", "/payments", "org/", "org/foo/bar", "org with spaces/repo"):
        with pytest.raises(ValidationError, match="full_name must be 'owner/name'"):
            RepositoryLinkRequest(installation_id=1, full_name=bad)


def test_link_request_allows_dots_and_hyphens_in_names() -> None:
    payload = RepositoryLinkRequest(installation_id=1, full_name="my-org/my.svc-v2")
    assert payload.full_name == "my-org/my.svc-v2"
