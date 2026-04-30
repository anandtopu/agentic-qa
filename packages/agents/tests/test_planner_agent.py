"""Unit tests for PlannerAgent — Story 1.3.1."""

from __future__ import annotations

import json
import uuid

import pytest

from qaforge_agents.llm.client import LLMClient
from qaforge_agents.llm.providers.mock import MockProvider, MockTurn
from qaforge_agents.llm.recorder import InMemoryRecorder
from qaforge_agents.llm.types import ModelSpec, Tier
from qaforge_agents.planner import PlannerAgent, PlannerInput
from qaforge_agents.planner.schema import PlannerTestPlan, TestCaseType


def _client(content: str) -> LLMClient:
    provider = MockProvider([MockTurn(content=content)])
    return LLMClient(
        providers={"mock": provider},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.HIGH: [ModelSpec(provider="mock", model="mock-model")],
            Tier.MID: [ModelSpec(provider="mock", model="mock-model")],
            Tier.LOW: [ModelSpec(provider="mock", model="mock-model")],
        },
    )


def _valid_plan_json(*, with_negative: bool = True) -> str:
    payload = {
        "summary": "Login flow regression plan",
        "coverage_areas": ["auth"],
        "test_cases": [
            {
                "title": "Successful login redirects to /home",
                "type": "api",
                "priority": "high",
                "preconditions": ["valid credentials"],
                "steps": ["POST /login"],
                "expected_result": "302 to /home",
                "automation_candidate": True,
                "tags": ["auth"],
            }
        ],
        "open_questions": [],
    }
    if with_negative:
        payload["test_cases"].append(
            {
                "title": "Invalid password returns 401",
                "type": "negative",
                "priority": "high",
                "preconditions": [],
                "steps": ["POST /login with wrong password"],
                "expected_result": "401 with auth fail message",
                "automation_candidate": True,
                "tags": ["auth"],
            }
        )
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_planner_returns_validated_plan() -> None:
    agent = PlannerAgent(_client(_valid_plan_json()))
    output = await agent.plan(
        PlannerInput(
            requirement_id=uuid.uuid4(),
            requirement_type="user_story",
            requirement_summary="Login flow",
            parsed_payload={"body": "POST /login"},
        )
    )
    assert isinstance(output.plan, PlannerTestPlan)
    assert output.plan.summary.startswith("Login flow")
    assert any(c.type is TestCaseType.NEGATIVE for c in output.plan.test_cases)


@pytest.mark.asyncio
async def test_planner_appends_heuristic_open_questions() -> None:
    """Plan with no negative case should pick up a heuristic open question."""
    agent = PlannerAgent(_client(_valid_plan_json(with_negative=False)))
    output = await agent.plan(
        PlannerInput(
            requirement_id=uuid.uuid4(),
            requirement_type="user_story",
            requirement_summary="Login flow",
            parsed_payload={"body": "POST /login"},
        )
    )
    questions = " ".join(output.plan.open_questions).lower()
    assert "negative" in questions


@pytest.mark.asyncio
async def test_planner_records_usage() -> None:
    agent = PlannerAgent(_client(_valid_plan_json()))
    output = await agent.plan(
        PlannerInput(
            requirement_id=uuid.uuid4(),
            requirement_type="openapi",
            requirement_summary="Payments API",
            parsed_payload={"endpoints": []},
        )
    )
    assert output.usage.provider == "mock"
    assert output.usage.model == "mock-model"


@pytest.mark.asyncio
async def test_planner_rejects_invalid_llm_output() -> None:
    """If the model returns a payload that violates the schema, LLMClient raises."""
    bad_json = json.dumps({"summary": "x", "test_cases": []})  # min_length=1 fails
    agent = PlannerAgent(_client(bad_json))
    from qaforge_agents.llm.client import StructuredOutputError

    with pytest.raises(StructuredOutputError):
        await agent.plan(
            PlannerInput(
                requirement_id=uuid.uuid4(),
                requirement_type="user_story",
                requirement_summary="X",
                parsed_payload={},
            )
        )
