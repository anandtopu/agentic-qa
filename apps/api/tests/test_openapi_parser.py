"""Unit tests for the OpenAPI parser — Story 1.2.3."""

from __future__ import annotations

import json

import pytest

from qaforge_api.requirements.parsers import openapi
from qaforge_api.requirements.parsers.base import ParseError

_OPENAPI_3_0 = """
openapi: 3.0.3
info:
  title: Payments API
  version: 1.0.0
paths:
  /charge:
    post:
      operationId: createCharge
      summary: Create a charge
      tags: [payments]
  /charge/{id}:
    get:
      operationId: getCharge
      summary: Get a charge
"""

_OPENAPI_3_1 = """
openapi: 3.1.0
info:
  title: Tiny
paths:
  /:
    get:
      operationId: root
"""


def test_parses_openapi_3_0_yaml_and_preserves_operation_ids() -> None:
    parsed = openapi.parse({"body": _OPENAPI_3_0})
    op_ids = [e["operation_id"] for e in parsed.payload["endpoints"]]
    assert op_ids == ["createCharge", "getCharge"]
    assert parsed.payload["endpoint_count"] == 2
    assert parsed.summary == "Payments API"


def test_parses_openapi_3_1() -> None:
    parsed = openapi.parse({"body": _OPENAPI_3_1})
    assert parsed.payload["version"] == "3.1.0"


def test_accepts_pre_parsed_dict() -> None:
    document = {
        "openapi": "3.0.0",
        "info": {"title": "X"},
        "paths": {"/x": {"get": {"operationId": "getX"}}},
    }
    parsed = openapi.parse({"document": document})
    assert parsed.payload["endpoints"][0]["operation_id"] == "getX"


def test_accepts_json_body() -> None:
    body = json.dumps(
        {
            "openapi": "3.0.0",
            "info": {"title": "JSON"},
            "paths": {"/p": {"get": {"operationId": "p"}}},
        }
    )
    parsed = openapi.parse({"body": body})
    assert parsed.payload["title"] == "JSON"


def test_rejects_unsupported_version() -> None:
    with pytest.raises(ParseError, match="openapi"):
        openapi.parse({"body": "openapi: 2.0\npaths: {}\n"})


def test_rejects_missing_paths() -> None:
    with pytest.raises(ParseError, match="paths"):
        openapi.parse({"body": "openapi: 3.0.0\ninfo: {title: x}\n"})


def test_rejects_paths_with_no_operations() -> None:
    body = """
openapi: 3.0.0
info: {title: x}
paths:
  /empty:
    parameters: []
"""
    with pytest.raises(ParseError, match="no operations"):
        openapi.parse({"body": body})
