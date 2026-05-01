"""Unit tests for the PR diff parser — Story 1.2.1."""

from __future__ import annotations

import pytest

from aqao_api.requirements.parsers import pr_diff
from aqao_api.requirements.parsers.base import ParseError


def _github_payload() -> dict[str, object]:
    return {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "title": "Add login flow",
            "body": "Closes #100",
            "head": {"sha": "abc123def456", "ref": "feature/login"},
            "base": {
                "ref": "main",
                "repo": {"full_name": "aqao/sample-app"},
            },
        },
        "changed_files": ["app/login.py", "tests/test_login.py"],
    }


def test_parses_github_webhook_shape() -> None:
    parsed = pr_diff.parse(_github_payload())
    assert parsed.commit_sha == "abc123def456"
    assert parsed.payload["pr_number"] == 42
    assert parsed.payload["head_branch"] == "feature/login"
    assert parsed.payload["base_branch"] == "main"
    assert parsed.payload["repository_full_name"] == "aqao/sample-app"
    assert parsed.payload["action"] == "opened"
    assert "PR #42" in parsed.summary


def test_parses_manual_payload_shape() -> None:
    parsed = pr_diff.parse(
        {
            "pr_number": 7,
            "commit_sha": "deadbeef",
            "head_branch": "feature/x",
            "base_branch": "main",
            "title": "Manual",
            "changed_files": ["a.py"],
        }
    )
    assert parsed.commit_sha == "deadbeef"
    assert parsed.payload["changed_files"] == ["a.py"]


def test_rejects_missing_pr_number() -> None:
    with pytest.raises(ParseError, match="pr_number"):
        pr_diff.parse({"commit_sha": "abc"})


def test_rejects_missing_commit_sha() -> None:
    with pytest.raises(ParseError, match="commit_sha"):
        pr_diff.parse({"pr_number": 1})


def test_changed_files_must_be_list() -> None:
    with pytest.raises(ParseError, match="changed_files"):
        pr_diff.parse({"pr_number": 1, "commit_sha": "abc", "changed_files": "not-a-list"})
