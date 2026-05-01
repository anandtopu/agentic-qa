"""Unit tests for the Postman parser — Story 1.2.3."""

from __future__ import annotations

import json

import pytest

from aqao_api.requirements.parsers import postman
from aqao_api.requirements.parsers.base import ParseError

_COLLECTION = {
    "info": {
        "name": "Payments",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [
        {"key": "baseUrl", "value": "https://api.example.com"},
        {"key": "version", "value": "v1"},
    ],
    "item": [
        {
            "name": "Charges",
            "item": [
                {
                    "name": "Create charge",
                    "request": {
                        "method": "POST",
                        "url": "{{baseUrl}}/{{version}}/charge",
                    },
                }
            ],
        },
        {
            "name": "Health",
            "request": {"method": "GET", "url": "{{baseUrl}}/healthz"},
        },
    ],
}


def test_parses_v2_1_collection_and_resolves_variables() -> None:
    parsed = postman.parse({"document": _COLLECTION})
    requests = parsed.payload["requests"]
    assert len(requests) == 2
    create = next(r for r in requests if r["name"] == "Create charge")
    assert create["url"] == "https://api.example.com/v1/charge"
    assert create["folder"] == ["Charges"]
    health = next(r for r in requests if r["name"] == "Health")
    assert health["url"] == "https://api.example.com/healthz"


def test_unresolved_variables_kept_verbatim() -> None:
    document = dict(_COLLECTION)
    # Drop the resolution for `version` to confirm fallback behaviour.
    document = {
        **document,
        "variable": [{"key": "baseUrl", "value": "https://x.example"}],
    }
    parsed = postman.parse({"document": document})
    create = next(r for r in parsed.payload["requests"] if r["name"] == "Create charge")
    assert "{{version}}" in create["url"]


def test_accepts_v2_0_schema() -> None:
    document = dict(_COLLECTION)
    document = {
        **document,
        "info": {
            **document["info"],  # type: ignore[arg-type]
            "schema": "https://schema.getpostman.com/json/collection/v2.0.0/collection.json",
        },
    }
    parsed = postman.parse({"document": document})
    assert parsed.payload["schema"].endswith("v2.0.0/collection.json")


def test_rejects_missing_schema() -> None:
    document = dict(_COLLECTION)
    document = {**document, "info": {"name": "x"}}
    with pytest.raises(ParseError, match="schema"):
        postman.parse({"document": document})


def test_rejects_collection_with_no_requests() -> None:
    document = {
        "info": {
            "name": "Empty",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": "Empty folder", "item": []}],
    }
    with pytest.raises(ParseError, match="no requests"):
        postman.parse({"document": document})


def test_accepts_string_body() -> None:
    parsed = postman.parse({"body": json.dumps(_COLLECTION)})
    assert parsed.payload["request_count"] == 2
