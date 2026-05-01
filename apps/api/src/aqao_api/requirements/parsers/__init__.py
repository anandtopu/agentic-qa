"""Per-type requirement parsers.

Each module exposes a single ``parse(raw)`` function that returns a
:class:`ParsedRequirement` or raises :class:`ParseError`. The
:func:`parse_for` registry dispatches by :class:`RequirementType`.
"""

from aqao_api.requirements.parsers.base import ParsedRequirement, ParseError
from aqao_api.requirements.parsers.registry import parse_for

__all__ = ["ParseError", "ParsedRequirement", "parse_for"]
