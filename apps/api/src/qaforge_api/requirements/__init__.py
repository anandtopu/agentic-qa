"""Requirement ingestion — Story 1.2.

Each input artifact (PR diff, user story, OpenAPI, Postman, SQL schema)
flows through a per-type parser that produces a normalised JSONB shape
the agents downstream can consume uniformly.
"""

from qaforge_api.requirements.parsers import (
    ParsedRequirement,
    ParseError,
    parse_for,
)

__all__ = ["ParseError", "ParsedRequirement", "parse_for"]
