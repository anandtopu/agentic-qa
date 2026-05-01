"""Shared types for requirement parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ParseError(Exception):
    """Raised when an input fails its type's parser.

    ``field`` is a dotted path the UI can highlight; leave as ``None``
    when the failure is global (e.g. malformed JSON).
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass(slots=True)
class ParsedRequirement:
    """Normalised parser output stored in ``requirements.parsed``."""

    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_ref: str | None = None
    commit_sha: str | None = None
