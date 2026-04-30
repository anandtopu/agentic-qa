"""Unit tests for the user-story parser — Story 1.2.2."""

from __future__ import annotations

import pytest

from qaforge_api.requirements.parsers import user_story
from qaforge_api.requirements.parsers.base import ParseError

_STORY_AC_BULLETS = """
# Login flow

As a user, I want to sign in so that I can access my account.

## Acceptance Criteria

- [ ] User can sign in with email + password
- [x] Invalid credentials show an error
- Account locks after 5 failed attempts
"""

_STORY_GHERKIN = """
# Reset password

Given I am on the reset page
When I submit my email
Then I receive a reset link by email
And the link expires after 24 hours
"""

_STORY_BOTH = """
# Multifactor

## Acceptance Criteria

- MFA is required when login from a new device

Given a logged-in user
When they enable MFA
Then subsequent logins require a TOTP code
"""

_STORY_NO_AC = """
# Random thoughts

Just a paragraph with no structure.
"""


def test_extracts_acceptance_criteria_bullets() -> None:
    parsed = user_story.parse({"body": _STORY_AC_BULLETS})
    bullets = parsed.payload["acceptance_criteria"]
    assert len(bullets) == 3
    assert bullets[0]["text"].startswith("User can sign in")
    assert bullets[0]["checked"] is False
    assert bullets[1]["checked"] is True
    assert parsed.payload["title"] == "Login flow"


def test_extracts_gherkin_lines() -> None:
    parsed = user_story.parse({"body": _STORY_GHERKIN})
    gherkin = parsed.payload["gherkin"]
    keywords = [g["keyword"] for g in gherkin]
    assert keywords == ["given", "when", "then", "and"]


def test_handles_mixed_ac_and_gherkin() -> None:
    parsed = user_story.parse({"body": _STORY_BOTH})
    assert parsed.payload["acceptance_criteria"]
    assert parsed.payload["gherkin"]


def test_rejects_body_with_no_ac_or_gherkin() -> None:
    with pytest.raises(ParseError, match="no acceptance criteria"):
        user_story.parse({"body": _STORY_NO_AC})


def test_rejects_empty_body() -> None:
    with pytest.raises(ParseError, match="body"):
        user_story.parse({"body": ""})


def test_ac_section_ends_at_next_heading() -> None:
    body = """
## Acceptance Criteria

- First AC
- Second AC

## Notes

- This bullet should not be in AC.
"""
    parsed = user_story.parse({"body": body})
    texts = [b["text"] for b in parsed.payload["acceptance_criteria"]]
    assert texts == ["First AC", "Second AC"]
