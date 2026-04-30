"""Postman Collection v2.x parser.

Validates the minimum shape (``info.schema`` + non-empty ``item``) and
flattens nested folders into a list of requests. Resolves ``{{var}}``
references against the collection-level ``variable`` array (Story 1.2.3 AC).
"""

from __future__ import annotations

import json
import re
from typing import Any

from qaforge_api.requirements.parsers.base import ParsedRequirement, ParseError

_VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
_SUPPORTED_SCHEMAS = (
    "https://schema.getpostman.com/json/collection/v2.0.0/collection.json",
    "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
)


def parse(raw: dict[str, Any]) -> ParsedRequirement:
    document = _resolve_document(raw)

    info = document.get("info") or {}
    schema = info.get("schema") if isinstance(info, dict) else None
    if not isinstance(schema, str) or schema not in _SUPPORTED_SCHEMAS:
        raise ParseError(
            "Postman collection must declare info.schema as v2.0 or v2.1",
            field="info.schema",
        )

    name = info.get("name") if isinstance(info, dict) else None
    items = document.get("item")
    if not isinstance(items, list) or not items:
        raise ParseError("Postman collection has no items", field="item")

    variables = _flatten_variables(document.get("variable"))
    requests: list[dict[str, Any]] = []
    _walk(items, variables, requests, folder=())

    if not requests:
        raise ParseError(
            "Postman collection contains folders but no requests",
            field="item",
        )

    return ParsedRequirement(
        summary=str(name or "Postman collection"),
        source_ref=raw.get("source_ref"),
        payload={
            "name": name,
            "schema": schema,
            "variables": variables,
            "request_count": len(requests),
            "requests": requests,
        },
    )


def _resolve_document(raw: dict[str, Any]) -> dict[str, Any]:
    if "document" in raw and isinstance(raw["document"], dict):
        return dict(raw["document"])
    body = raw.get("body") or raw.get("content")
    if not isinstance(body, str) or not body.strip():
        raise ParseError("Postman body is required", field="body")
    try:
        loaded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Postman JSON parse failed: {exc.msg}", field="body") from exc
    if not isinstance(loaded, dict):
        raise ParseError("Postman document must be a JSON object", field="body")
    return loaded


def _flatten_variables(raw: object) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}
    out: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        value = entry.get("value")
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def _walk(
    items: list[Any],
    variables: dict[str, str],
    out: list[dict[str, Any]],
    *,
    folder: tuple[str, ...],
) -> None:
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("item"), list):
            sub_name = str(entry.get("name") or "")
            _walk(entry["item"], variables, out, folder=(*folder, sub_name))
            continue
        request = entry.get("request")
        if isinstance(request, str):
            url = _resolve(request, variables)
            method = "GET"
        elif isinstance(request, dict):
            url = _request_url(request, variables)
            method = str(request.get("method") or "GET").upper()
        else:
            continue
        out.append(
            {
                "name": entry.get("name") or "",
                "method": method,
                "url": url,
                "folder": list(folder),
            }
        )


def _request_url(request: dict[str, Any], variables: dict[str, str]) -> str:
    raw_url = request.get("url")
    if isinstance(raw_url, str):
        return _resolve(raw_url, variables)
    if isinstance(raw_url, dict):
        if isinstance(raw_url.get("raw"), str):
            return _resolve(raw_url["raw"], variables)
        host = raw_url.get("host") or []
        path = raw_url.get("path") or []
        parts: list[str] = []
        if isinstance(host, list):
            parts.append(".".join(str(p) for p in host))
        elif isinstance(host, str):
            parts.append(host)
        if isinstance(path, list):
            parts.append("/" + "/".join(str(p) for p in path))
        elif isinstance(path, str):
            parts.append(path)
        return _resolve("".join(parts), variables)
    return ""


def _resolve(value: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1), match.group(0))

    return _VAR_PATTERN.sub(replace, value)
