"""Agentic QA Orchestrator Python SDK — Story 5.3.

Thin client wrapping the Agentic QA Orchestrator REST surface. Two clients with the
same shape:

* :class:`AQAOClient` — synchronous, wraps ``httpx.Client``.
* :class:`AsyncAQAOClient` — async, wraps ``httpx.AsyncClient``.

Both share auth + retry + idempotency-key logic so callers don't
re-implement them. The error hierarchy mirrors HTTP status codes
1:1 so callers can ``except NotFoundError`` instead of pattern-
matching on ``response.status_code``.
"""

from aqao_sdk.client import (
    AsyncAQAOClient,
    AQAOClient,
)
from aqao_sdk.errors import (
    AuthError,
    ConflictError,
    NotFoundError,
    PermissionError_,
    AQAOError,
    RateLimitError,
    ValidationError,
)

__all__ = [
    "AsyncAQAOClient",
    "AuthError",
    "ConflictError",
    "NotFoundError",
    "PermissionError_",
    "AQAOClient",
    "AQAOError",
    "RateLimitError",
    "ValidationError",
]
