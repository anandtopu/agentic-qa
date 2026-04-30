"""YAML → :class:`AgentPolicy` loader with field-level error reporting.

The two failure modes are kept distinct so the API layer can produce a
useful 422 body that points at the problem:

* :class:`PolicyParseError` — the YAML itself is malformed.
* :class:`PolicyValidationError` — the YAML parsed but doesn't match
  the schema (wrong types, unknown fields, out-of-range values).
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import ValidationError

from qaforge_api.policies.errors import (
    FieldError,
    PolicyParseError,
    PolicyValidationError,
)
from qaforge_api.policies.schema import AgentPolicy


def load_policy_yaml(source: str) -> AgentPolicy:
    """Parse a YAML policy document and return a validated :class:`AgentPolicy`.

    Accepts both a top-level ``policy:`` key (PRD §10.3 idiom) and a
    flat top-level mapping for ergonomics.
    """
    try:
        loaded = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        line, column = _extract_yaml_position(exc)
        raise PolicyParseError(str(exc), line=line, column=column) from exc

    if loaded is None:
        raise PolicyValidationError(
            [
                FieldError(
                    location=(),
                    message="policy document is empty",
                    type="value_error.empty",
                )
            ]
        )

    if not isinstance(loaded, dict):
        raise PolicyValidationError(
            [
                FieldError(
                    location=(),
                    message="policy document must be a mapping",
                    type="type_error.dict",
                )
            ]
        )

    payload: dict[str, Any] = loaded.get("policy", loaded) if isinstance(loaded, dict) else loaded
    if not isinstance(payload, dict):
        raise PolicyValidationError(
            [
                FieldError(
                    location=("policy",),
                    message="`policy` key must hold a mapping",
                    type="type_error.dict",
                )
            ]
        )

    try:
        return AgentPolicy.model_validate(payload)
    except ValidationError as exc:
        raise PolicyValidationError(_translate_pydantic_errors(exc)) from exc


def _translate_pydantic_errors(exc: ValidationError) -> list[FieldError]:
    out: list[FieldError] = []
    for err in exc.errors(include_url=False):
        loc = tuple(str(p) for p in err.get("loc", ()))
        out.append(
            FieldError(
                location=loc,
                message=str(err.get("msg", "")),
                type=str(err.get("type", "")),
            )
        )
    return out


def _extract_yaml_position(exc: yaml.YAMLError) -> tuple[int | None, int | None]:
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return (None, None)
    return (int(mark.line) + 1, int(mark.column) + 1)
