"""Unit tests for the credential broker — Story 1.4.3."""

from __future__ import annotations

import asyncio
import uuid

from qaforge_tools.credentials import InMemoryCredentialBroker

WORKSPACE = uuid.uuid4()


def test_issue_returns_all_values_when_no_keys_specified() -> None:
    broker = InMemoryCredentialBroker()
    broker.load_workspace(
        workspace_id=WORKSPACE,
        environment="staging",
        variables={"API_TOKEN": "abc123secret", "BASE_URL": "https://x.example"},
    )

    bundle = asyncio.run(broker.issue(workspace_id=WORKSPACE, environment="staging"))
    assert bundle.values == {
        "API_TOKEN": "abc123secret",
        "BASE_URL": "https://x.example",
    }
    assert bundle.workspace_id == WORKSPACE


def test_issue_filters_to_requested_keys() -> None:
    broker = InMemoryCredentialBroker()
    broker.load_workspace(
        workspace_id=WORKSPACE,
        environment="staging",
        variables={"A": "1", "B": "2", "C": "3"},
    )

    bundle = asyncio.run(
        broker.issue(workspace_id=WORKSPACE, environment="staging", keys=["A", "C"])
    )
    assert bundle.values == {"A": "1", "C": "3"}


def test_issue_returns_empty_for_unknown_environment() -> None:
    broker = InMemoryCredentialBroker()
    bundle = asyncio.run(broker.issue(workspace_id=WORKSPACE, environment="staging"))
    assert bundle.values == {}


def test_redactor_attached_to_bundle_scrubs_values() -> None:
    broker = InMemoryCredentialBroker()
    broker.load_workspace(
        workspace_id=WORKSPACE,
        environment="staging",
        variables={"API_TOKEN": "topsecret-xyz-12345"},
    )

    bundle = asyncio.run(broker.issue(workspace_id=WORKSPACE, environment="staging"))
    redacted = bundle.redactor.redact("Sending request with token=topsecret-xyz-12345 — done.")
    assert "topsecret-xyz-12345" not in redacted
    assert "[REDACTED]" in redacted


def test_temporary_context_isolates_state() -> None:
    broker = InMemoryCredentialBroker()
    broker.load_workspace(
        workspace_id=WORKSPACE,
        environment="prod",
        variables={"keep": "kept"},
    )
    with broker.temporary(
        workspace_id=WORKSPACE,
        environment="prod",
        variables={"only-during": "x"},
    ):
        bundle = asyncio.run(broker.issue(workspace_id=WORKSPACE, environment="prod"))
        assert bundle.values == {"only-during": "x"}

    bundle_after = asyncio.run(broker.issue(workspace_id=WORKSPACE, environment="prod"))
    assert bundle_after.values == {"keep": "kept"}
