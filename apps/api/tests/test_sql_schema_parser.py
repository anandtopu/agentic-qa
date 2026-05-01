"""Unit tests for the SQL schema parser — Story 1.2.3."""

from __future__ import annotations

import pytest

from aqao_api.requirements.parsers import sql_schema
from aqao_api.requirements.parsers.base import ParseError

_DDL = """
CREATE TABLE users (
    id UUID NOT NULL PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    name VARCHAR(200),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def test_parses_two_tables() -> None:
    parsed = sql_schema.parse({"body": _DDL})
    tables = parsed.payload["tables"]
    assert {t["name"] for t in tables} == {"users", "orders"}


def test_extracts_column_types_and_nullability() -> None:
    parsed = sql_schema.parse({"body": _DDL})
    users = next(t for t in parsed.payload["tables"] if t["name"] == "users")
    cols = {c["name"]: c for c in users["columns"]}
    assert cols["id"]["type"] == "UUID"
    assert cols["id"]["nullable"] is False
    assert cols["id"]["primary_key"] is True
    assert cols["email"]["type"].startswith("VARCHAR")
    assert cols["name"]["nullable"] is True


def test_skips_table_constraints_in_column_list() -> None:
    parsed = sql_schema.parse({"body": _DDL})
    users = next(t for t in parsed.payload["tables"] if t["name"] == "users")
    col_names = [c["name"] for c in users["columns"]]
    assert "uq_users_email" not in col_names


def test_handles_quoted_identifiers() -> None:
    parsed = sql_schema.parse({"body": 'CREATE TABLE "Mixed Case" ( "id" INT NOT NULL );'})
    table = parsed.payload["tables"][0]
    assert table["name"] == "Mixed Case"
    assert table["columns"][0]["name"] == "id"


def test_rejects_body_with_no_create_table() -> None:
    with pytest.raises(ParseError, match="no CREATE TABLE"):
        sql_schema.parse({"body": "SELECT 1;"})


def test_rejects_empty_body() -> None:
    with pytest.raises(ParseError, match="body"):
        sql_schema.parse({"body": ""})
