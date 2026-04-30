"""SDK error hierarchy mirroring HTTP status codes."""

from __future__ import annotations

from typing import Any


class QAForgeError(RuntimeError):
    """Base class — every other SDK error inherits from this."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        trace_id: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.trace_id = trace_id
        self.details = list(details or [])


class AuthError(QAForgeError):
    """401 — missing or invalid token / tenant header."""


class PermissionError_(QAForgeError):  # noqa: N801 - mirrors built-in but distinct
    """403 — authenticated but role lacks the permission."""


class NotFoundError(QAForgeError):
    """404 — resource doesn't exist (or RLS hides it from this tenant)."""


class ConflictError(QAForgeError):
    """409 — approval already decided / idempotency-key body mismatch."""


class ValidationError(QAForgeError):
    """422 — typed body failed validation. ``details`` carries the
    field-level errors."""


class RateLimitError(QAForgeError):
    """429 — bulkhead saturated or per-tenant rate limit exceeded.

    ``retry_after_seconds`` is set when the server sent the
    ``Retry-After`` header.
    """

    def __init__(
        self, message: str, *, retry_after_seconds: float | None = None, **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


_STATUS_TO_ERROR: dict[int, type[QAForgeError]] = {
    401: AuthError,
    403: PermissionError_,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(
    *,
    status_code: int,
    message: str,
    trace_id: str | None,
    details: list[dict[str, Any]] | None,
    retry_after_seconds: float | None = None,
) -> QAForgeError:
    """Construct the right error subclass for an HTTP status."""
    cls = _STATUS_TO_ERROR.get(status_code, QAForgeError)
    if cls is RateLimitError:
        return RateLimitError(
            message,
            status_code=status_code,
            trace_id=trace_id,
            details=details,
            retry_after_seconds=retry_after_seconds,
        )
    return cls(
        message,
        status_code=status_code,
        trace_id=trace_id,
        details=details,
    )


__all__ = [
    "AuthError",
    "ConflictError",
    "NotFoundError",
    "PermissionError_",
    "QAForgeError",
    "RateLimitError",
    "ValidationError",
    "error_for_status",
]
