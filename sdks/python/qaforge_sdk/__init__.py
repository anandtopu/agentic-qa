"""QAForge Python SDK — Story 5.3.

Thin client wrapping the QAForge REST surface. Two clients with the
same shape:

* :class:`QAForgeClient` — synchronous, wraps ``httpx.Client``.
* :class:`AsyncQAForgeClient` — async, wraps ``httpx.AsyncClient``.

Both share auth + retry + idempotency-key logic so callers don't
re-implement them. The error hierarchy mirrors HTTP status codes
1:1 so callers can ``except NotFoundError`` instead of pattern-
matching on ``response.status_code``.
"""

from qaforge_sdk.client import (
    AsyncQAForgeClient,
    QAForgeClient,
)
from qaforge_sdk.errors import (
    AuthError,
    ConflictError,
    NotFoundError,
    PermissionError_,
    QAForgeError,
    RateLimitError,
    ValidationError,
)

__all__ = [
    "AsyncQAForgeClient",
    "AuthError",
    "ConflictError",
    "NotFoundError",
    "PermissionError_",
    "QAForgeClient",
    "QAForgeError",
    "RateLimitError",
    "ValidationError",
]
