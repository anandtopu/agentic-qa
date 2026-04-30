"""OpenAPI 3.x parser.

Validates the minimum surface: ``openapi`` version string and a non-empty
``paths`` mapping. Preserves every ``operationId`` (Story 1.2.3 AC) and
extracts a normalised endpoint list for downstream agents.

Accepts either JSON or YAML source, or an already-parsed dict.
"""

from __future__ import annotations

from typing import Any

import yaml

from qaforge_api.requirements.parsers.base import ParsedRequirement, ParseError

_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
}


def parse(raw: dict[str, Any]) -> ParsedRequirement:
    document = _resolve_document(raw)

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith(("3.0", "3.1")):
        raise ParseError(
            "expected `openapi: 3.0.x` or `openapi: 3.1.x`",
            field="openapi",
        )

    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ParseError(
            "OpenAPI document has no `paths` operations",
            field="paths",
        )

    info = document.get("info") or {}
    title = info.get("title") if isinstance(info, dict) else None

    endpoints: list[dict[str, Any]] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(op, dict):
                continue
            endpoints.append(
                {
                    "method": method.lower(),
                    "path": path,
                    "operation_id": op.get("operationId"),
                    "summary": op.get("summary"),
                    "tags": list(op.get("tags") or []),
                }
            )

    if not endpoints:
        raise ParseError(
            "OpenAPI document has no operations across its paths",
            field="paths",
        )

    return ParsedRequirement(
        summary=str(title or f"OpenAPI {version}"),
        source_ref=raw.get("source_ref"),
        payload={
            "version": version,
            "title": title,
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        },
    )


def _resolve_document(raw: dict[str, Any]) -> dict[str, Any]:
    if "document" in raw and isinstance(raw["document"], dict):
        return dict(raw["document"])
    body = raw.get("body") or raw.get("content")
    if not isinstance(body, str) or not body.strip():
        raise ParseError("OpenAPI body is required", field="body")
    try:
        loaded = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise ParseError(f"OpenAPI parse failed: {exc}", field="body") from exc
    if not isinstance(loaded, dict):
        raise ParseError(
            "OpenAPI document must be a JSON or YAML object",
            field="body",
        )
    return loaded
