"""Unit tests for service error types.

The router translates these into HTTP status codes, so the messages and
public attributes are part of the contract.
"""

from __future__ import annotations

from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ServiceError,
)


def test_resource_not_found_carries_resource_and_id() -> None:
    err = ResourceNotFoundError("workspace", "abc")
    assert isinstance(err, ServiceError)
    assert err.resource == "workspace"
    assert err.identifier == "abc"
    assert "workspace" in str(err)


def test_duplicate_resource_carries_field_and_value() -> None:
    err = DuplicateResourceError("workspace", "name", "Payments")
    assert isinstance(err, ServiceError)
    assert err.field == "name"
    assert err.value == "Payments"
    assert "Payments" in str(err)
