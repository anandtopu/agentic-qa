"""Unit tests for UiTesterAgent — Story 1.5.1."""

from __future__ import annotations

import json
import uuid

import pytest

from qaforge_agents.llm.client import LLMClient, StructuredOutputError
from qaforge_agents.llm.providers.mock import MockProvider, MockTurn
from qaforge_agents.llm.recorder import InMemoryRecorder
from qaforge_agents.llm.types import ModelSpec, Tier
from qaforge_agents.ui_tester import UiTesterAgent, UiTesterInput
from qaforge_agents.ui_tester.ts_validator import GeneratedSpecInvalid

_VALID_SOURCE = """\
import { test, expect } from '@playwright/test';

test('login succeeds', async ({ page }) => {
  const baseUrl = process.env.QAFORGE_UI_BASE_URL!;
  await page.goto(baseUrl + '/login');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Welcome')).toBeVisible();
});
"""

_BRITTLE_SOURCE = """\
import { test, expect } from '@playwright/test';

test('settings page', async ({ page }) => {
  const baseUrl = process.env.QAFORGE_UI_BASE_URL!;
  await page.goto(baseUrl);
  await page.locator('xpath=//a[1]').click();
  await page.locator('main > div > div > div > div > .label').click();
  await expect(page.getByText('Done')).toBeVisible();
});
"""


def _client(content: str) -> LLMClient:
    return LLMClient(
        providers={"mock": MockProvider([MockTurn(content=content)])},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [ModelSpec(provider="mock", model="mock-model")],
            Tier.HIGH: [ModelSpec(provider="mock", model="mock-model")],
            Tier.LOW: [ModelSpec(provider="mock", model="mock-model")],
        },
    )


def _spec_json(source: str) -> str:
    return json.dumps(
        {
            "framework": "@playwright/test",
            "spec_filename": "login.spec.ts",
            "source_code": source,
            "tests": [
                {
                    "test_case_title": "Successful login",
                    "title": "login succeeds",
                    "journey_steps": ["go to /login", "click Sign in"],
                    "expected_outcome": "Welcome banner visible",
                    "requires_auth": False,
                }
            ],
        }
    )


def _input() -> UiTesterInput:
    return UiTesterInput(
        test_plan_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        spec_filename="login.spec.ts",
        workspace_summary={"name": "Demo"},
        test_cases=[
            {
                "title": "Successful login",
                "type": "ui",
                "priority": "high",
                "expected_result": "Welcome banner visible",
                "steps": ["go to /login"],
            }
        ],
    )


@pytest.mark.asyncio
async def test_returns_validated_spec_with_no_fragility() -> None:
    agent = UiTesterAgent(_client(_spec_json(_VALID_SOURCE)))
    out = await agent.generate(_input())
    assert out.spec.spec_filename == "login.spec.ts"
    assert not out.fragility_report.has_findings


@pytest.mark.asyncio
async def test_attaches_fragility_findings_when_present() -> None:
    agent = UiTesterAgent(_client(_spec_json(_BRITTLE_SOURCE)))
    out = await agent.generate(_input())
    assert out.fragility_report.has_findings
    rules = {f.rule for f in out.fragility_report.findings}
    assert "xpath_locator" in rules


@pytest.mark.asyncio
async def test_rejects_invalid_ts_source() -> None:
    bad = "test('x', () => {});\n"  # missing playwright import + base url
    agent = UiTesterAgent(_client(_spec_json(bad)))
    with pytest.raises(GeneratedSpecInvalid):
        await agent.generate(_input())


@pytest.mark.asyncio
async def test_filters_out_pure_api_db_cases() -> None:
    inputs = UiTesterInput(
        test_plan_id=uuid.uuid4(),
        workspace_id=None,
        spec_filename="x.spec.ts",
        workspace_summary={},
        test_cases=[
            {"title": "API only", "type": "api", "expected_result": "200"},
            {"title": "DB only", "type": "db", "expected_result": "row count"},
            {"title": "Negative", "type": "negative", "expected_result": "401"},
        ],
    )
    agent = UiTesterAgent(_client(_spec_json(_VALID_SOURCE)))
    with pytest.raises(StructuredOutputError, match="no UI-tier"):
        # `negative` is in the relevant set, but here we pass only api+db+negative
        # — actually `negative` IS retained, so this would succeed. Adjust:
        inputs.test_cases = [c for c in inputs.test_cases if c["type"] in {"api", "db"}]
        await agent.generate(inputs)


def test_filter_relevant_includes_smoke_regression_integration() -> None:
    cases = [
        {"title": "x", "type": t}
        for t in ("ui", "smoke", "regression", "integration", "api", "db", "negative")
    ]
    relevant = UiTesterAgent.filter_relevant_cases(cases)
    types = {c["type"] for c in relevant}
    assert types == {"ui", "smoke", "regression", "integration"}
