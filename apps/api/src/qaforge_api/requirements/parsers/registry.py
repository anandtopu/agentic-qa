"""Parser registry — dispatch by :class:`RequirementType`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qaforge_api.db.models.requirement import RequirementType
from qaforge_api.requirements.parsers import (
    openapi,
    postman,
    pr_diff,
    sql_schema,
    user_story,
)
from qaforge_api.requirements.parsers.base import ParsedRequirement

_REGISTRY: dict[RequirementType, Callable[[dict[str, Any]], ParsedRequirement]] = {
    RequirementType.PR_DIFF: pr_diff.parse,
    RequirementType.USER_STORY: user_story.parse,
    RequirementType.OPENAPI: openapi.parse,
    RequirementType.POSTMAN: postman.parse,
    RequirementType.SQL_SCHEMA: sql_schema.parse,
}


def parse_for(requirement_type: RequirementType, raw: dict[str, Any]) -> ParsedRequirement:
    """Dispatch to the parser for a given requirement type."""
    parser = _REGISTRY.get(requirement_type)
    if parser is None:
        raise KeyError(f"no parser registered for {requirement_type!r}")
    return parser(raw)
