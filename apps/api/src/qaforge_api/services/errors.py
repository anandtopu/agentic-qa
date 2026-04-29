"""Service-layer errors.

Routers translate these to HTTP status codes; tests assert against the
Python types so the contract stays decoupled from FastAPI internals.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for service-layer failures the router can map cleanly."""


class ResourceNotFoundError(ServiceError):
    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} not found: {identifier!r}")
        self.resource = resource
        self.identifier = identifier


class DuplicateResourceError(ServiceError):
    def __init__(self, resource: str, field: str, value: object) -> None:
        super().__init__(f"{resource} with {field}={value!r} already exists")
        self.resource = resource
        self.field = field
        self.value = value
