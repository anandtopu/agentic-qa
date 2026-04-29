"""Unit tests for workspace API schemas.

These run without a database — they validate the Pydantic contract that
sits between HTTP and the service layer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from qaforge_api.db.models.workspace import ApplicationType
from qaforge_api.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)


class TestWorkspaceCreateRequest:
    def test_minimal_valid_payload(self) -> None:
        payload = WorkspaceCreateRequest(
            name="Payments",
            application_type=ApplicationType.WEB_API,
        )
        assert payload.name == "Payments"
        assert payload.default_branch == "main"
        assert payload.environments == []
        assert payload.repo_url is None
        assert payload.description is None

    def test_full_payload_round_trips(self) -> None:
        payload = WorkspaceCreateRequest(
            name="Payments",
            application_type=ApplicationType.WEB_API,
            repo_url="https://github.com/org/payments",
            default_branch="develop",
            environments=["dev", "staging", "prod"],
            description="Payments backend",
        )
        assert payload.environments == ["dev", "staging", "prod"]
        assert payload.repo_url == "https://github.com/org/payments"

    def test_environments_dedupe_and_strip(self) -> None:
        payload = WorkspaceCreateRequest(
            name="x",
            application_type=ApplicationType.WEB_API,
            environments=["  dev  ", "staging"],
        )
        assert payload.environments == ["dev", "staging"]

    def test_environments_reject_duplicates(self) -> None:
        with pytest.raises(ValidationError, match="environments must be unique"):
            WorkspaceCreateRequest(
                name="x",
                application_type=ApplicationType.WEB_API,
                environments=["dev", "dev"],
            )

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCreateRequest.model_validate({"application_type": "web_api"})

    def test_name_min_length(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCreateRequest(name="", application_type=ApplicationType.WEB_API)

    def test_application_type_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCreateRequest.model_validate({"name": "x", "application_type": "spaceship"})


class TestWorkspaceUpdateRequest:
    def test_empty_update_is_valid(self) -> None:
        payload = WorkspaceUpdateRequest()
        assert payload.model_dump(exclude_unset=True) == {}

    def test_partial_update_only_includes_provided_fields(self) -> None:
        payload = WorkspaceUpdateRequest(name="renamed")
        provided = payload.model_dump(exclude_unset=True)
        assert provided == {"name": "renamed"}

    def test_explicit_null_is_distinguishable_from_omission(self) -> None:
        payload = WorkspaceUpdateRequest.model_validate({"description": None})
        provided = payload.model_dump(exclude_unset=True)
        assert "description" in provided
        assert provided["description"] is None

        omitted = WorkspaceUpdateRequest()
        omitted_provided = omitted.model_dump(exclude_unset=True)
        assert "description" not in omitted_provided

    def test_unknown_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceUpdateRequest.model_validate({"junk": True})

    def test_environments_validation_applies(self) -> None:
        with pytest.raises(ValidationError, match="environments must be unique"):
            WorkspaceUpdateRequest(environments=["a", "a"])
