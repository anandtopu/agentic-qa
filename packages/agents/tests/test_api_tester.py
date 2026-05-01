"""Unit tests for ApiTesterAgent — Story 1.4.1."""

from __future__ import annotations

import json
import uuid

import pytest

from aqao_agents.api_tester import ApiTesterAgent, ApiTesterInput
from aqao_agents.api_tester.agent import GeneratedCodeInvalid
from aqao_agents.llm.client import LLMClient, StructuredOutputError
from aqao_agents.llm.providers.mock import MockProvider, MockTurn
from aqao_agents.llm.recorder import InMemoryRecorder
from aqao_agents.llm.types import ModelSpec, Tier

_VALID_SOURCE = """\
import os
import httpx
import pytest


BASE_URL = os.environ["AQAO_API_BASE_URL"]


def test_charge_succeeds() -> None:
    response = httpx.post(f"{BASE_URL}/charge", json={"amount": 100})
    assert response.status_code == 200
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


def _suite_json(source: str = _VALID_SOURCE) -> str:
    return json.dumps(
        {
            "framework": "pytest+httpx",
            "module_name": "test_charge",
            "source_code": source,
            "tests": [
                {
                    "test_case_title": "Successful charge",
                    "function_name": "test_charge_succeeds",
                    "method": "POST",
                    "path": "/charge",
                    "expected_status": 200,
                    "is_negative": False,
                    "requires_auth": True,
                }
            ],
        }
    )


def _input() -> ApiTesterInput:
    return ApiTesterInput(
        test_plan_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        module_name="test_charge",
        openapi_summary={
            "title": "Payments",
            "endpoints": [{"method": "post", "path": "/charge"}],
        },
        test_cases=[
            {
                "title": "Successful charge",
                "type": "api",
                "priority": "high",
                "expected_result": "200 OK",
            }
        ],
    )


@pytest.mark.asyncio
async def test_returns_validated_suite_for_valid_python() -> None:
    agent = ApiTesterAgent(_client(_suite_json()))
    out = await agent.generate(_input())
    assert out.suite.module_name == "test_charge"
    assert out.suite.tests[0].method == "POST"


@pytest.mark.asyncio
async def test_raises_when_generated_python_has_syntax_error() -> None:
    bad_source = "def test_x()\n    pass\n"  # missing colon
    agent = ApiTesterAgent(_client(_suite_json(bad_source)))
    with pytest.raises(GeneratedCodeInvalid, match="syntax error"):
        await agent.generate(_input())


@pytest.mark.asyncio
async def test_filters_out_ui_and_db_cases() -> None:
    inputs = ApiTesterInput(
        test_plan_id=uuid.uuid4(),
        workspace_id=None,
        module_name="test_x",
        openapi_summary={},
        test_cases=[
            {"title": "UI flow", "type": "ui", "expected_result": "ok"},
            {"title": "DB check", "type": "db", "expected_result": "ok"},
        ],
    )
    agent = ApiTesterAgent(_client(_suite_json()))
    with pytest.raises(StructuredOutputError, match="no API-tier"):
        await agent.generate(inputs)


def test_filter_relevant_keeps_api_integration_negative_regression_smoke() -> None:
    cases = [
        {"title": "x", "type": t}
        for t in ("api", "integration", "negative", "regression", "smoke", "ui", "db")
    ]
    relevant = ApiTesterAgent.filter_relevant_cases(cases)
    types = {c["type"] for c in relevant}
    assert types == {"api", "integration", "negative", "regression", "smoke"}
