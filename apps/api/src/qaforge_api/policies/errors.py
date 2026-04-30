"""Policy parsing / validation errors with field-pointer detail."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FieldError:
    """One field-level problem suitable for a 422 response body."""

    location: tuple[str, ...]
    message: str
    type: str

    def to_dict(self) -> dict[str, object]:
        return {
            "loc": list(self.location),
            "msg": self.message,
            "type": self.type,
        }


class PolicyParseError(Exception):
    """Raised when the YAML itself is malformed (line/column included)."""

    def __init__(self, message: str, *, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


class PolicyValidationError(Exception):
    """Raised when the YAML is well-formed but violates the AgentPolicy schema."""

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__(f"{len(errors)} field(s) failed validation")
        self.errors = errors
