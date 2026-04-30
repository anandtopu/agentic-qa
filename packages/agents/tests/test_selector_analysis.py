"""Unit tests for the selector fragility analyzer — Story 1.5.3."""

from __future__ import annotations

from qaforge_agents.ui_tester.selector_analysis import analyse_selectors


def test_flags_xpath_locator() -> None:
    spec = """\
test('x', async ({ page }) => {
  await page.locator('xpath=//button[1]').click();
});
"""
    report = analyse_selectors(spec)
    rules = {f.rule for f in report.findings}
    assert "xpath_locator" in rules


def test_flags_xpath_double_slash() -> None:
    spec = """\
test('x', async ({ page }) => {
  await page.locator('//div[@class="foo"]').click();
});
"""
    report = analyse_selectors(spec)
    rules = {f.rule for f in report.findings}
    assert "xpath_double_slash" in rules


def test_flags_deep_nth_child_above_threshold() -> None:
    spec = "  await page.locator('div:nth-child(7)').click();"
    report = analyse_selectors(spec)
    assert any(f.rule == "deep_nth_child" for f in report.findings)


def test_does_not_flag_shallow_nth_child() -> None:
    spec = "  await page.locator('li:nth-child(2)').click();"
    report = analyse_selectors(spec)
    assert not any(f.rule == "deep_nth_child" for f in report.findings)


def test_flags_deep_descendant_chain() -> None:
    spec = "  await page.locator('main > div > div > div > div > span').first();"
    report = analyse_selectors(spec)
    assert any(f.rule == "deep_descendant_chain" for f in report.findings)


def test_flags_class_only_selector() -> None:
    spec = "  await page.locator('.btn-primary').click();"
    report = analyse_selectors(spec)
    assert any(f.rule == "class_selector" for f in report.findings)


def test_flags_text_with_id_suffix() -> None:
    spec = "  await page.getByText('Order #12345').click();"
    report = analyse_selectors(spec)
    assert any(f.rule == "text_with_id_suffix" for f in report.findings)


def test_clean_spec_returns_no_findings() -> None:
    spec = """\
import { test, expect } from '@playwright/test';

test('login', async ({ page }) => {
  await page.goto(process.env.QAFORGE_UI_BASE_URL!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByTestId('email-input').fill('user@example.com');
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""
    report = analyse_selectors(spec)
    assert not report.has_findings


def test_summary_groups_by_rule() -> None:
    spec = """\
await page.locator('xpath=//a[1]').click();
await page.locator('//button').click();
await page.locator('div:nth-child(8)').click();
"""
    report = analyse_selectors(spec)
    summary = report.summary()
    assert summary.get("xpath_locator", 0) >= 1
    assert summary.get("xpath_double_slash", 0) >= 1
    assert summary.get("deep_nth_child", 0) >= 1
