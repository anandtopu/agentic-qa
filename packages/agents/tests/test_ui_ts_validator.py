"""Unit tests for the heuristic Playwright TS validator — Story 1.5.1."""

from __future__ import annotations

import pytest

from aqao_agents.ui_tester.ts_validator import (
    GeneratedSpecInvalid,
    validate_spec,
)

_VALID = """\
import { test, expect } from '@playwright/test';

test('login flow', async ({ page }) => {
  const baseUrl = process.env.AQAO_UI_BASE_URL!;
  await page.goto(baseUrl + '/login');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""


def test_valid_spec_passes() -> None:
    validate_spec(_VALID)


def test_rejects_empty_source() -> None:
    with pytest.raises(GeneratedSpecInvalid, match="empty"):
        validate_spec("")


def test_rejects_missing_playwright_import() -> None:
    spec = """\
test('x', () => { process.env.AQAO_UI_BASE_URL });
"""
    with pytest.raises(GeneratedSpecInvalid, match="@playwright/test"):
        validate_spec(spec)


def test_rejects_missing_base_url_reference() -> None:
    spec = """\
import { test } from '@playwright/test';
test('x', () => {});
"""
    with pytest.raises(GeneratedSpecInvalid, match="AQAO_UI_BASE_URL"):
        validate_spec(spec)


def test_rejects_python_def_keyword() -> None:
    spec = """\
import { test } from '@playwright/test';
def foo(): pass
test('x', () => { process.env.AQAO_UI_BASE_URL });
"""
    with pytest.raises(GeneratedSpecInvalid, match="Python-style 'def '"):
        validate_spec(spec)


def test_rejects_python_assert() -> None:
    spec = """\
import { test } from '@playwright/test';
assert something_true
test('x', () => { process.env.AQAO_UI_BASE_URL });
"""
    with pytest.raises(GeneratedSpecInvalid, match="assert"):
        validate_spec(spec)


def test_rejects_unbalanced_brace() -> None:
    spec = """\
import { test } from '@playwright/test';
test('x', () => { process.env.AQAO_UI_BASE_URL
"""
    with pytest.raises(GeneratedSpecInvalid, match="unbalanced"):
        validate_spec(spec)


def test_rejects_no_test_calls() -> None:
    spec = """\
import { test } from '@playwright/test';
const baseUrl = process.env.AQAO_UI_BASE_URL;
"""
    with pytest.raises(GeneratedSpecInvalid, match="test"):
        validate_spec(spec)


def test_string_braces_dont_break_balancer() -> None:
    """Open brace inside a string literal must not unbalance the global counter."""
    spec = """\
import { test } from '@playwright/test';
test('x', async ({ page }) => {
  const baseUrl = process.env.AQAO_UI_BASE_URL!;
  console.log("opens with { brace");
});
"""
    validate_spec(spec)
