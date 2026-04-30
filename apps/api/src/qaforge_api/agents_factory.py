"""Wire-up for agent dependencies (FastAPI Depends targets).

Holds the singleton :class:`LLMClient` and the per-agent factories. Tests
override these via ``app.dependency_overrides`` to inject mocks.
"""

from __future__ import annotations

from functools import lru_cache

from qaforge_agents.api_tester import ApiTesterAgent
from qaforge_agents.classifier import (
    FailureClassifierAgent,
    HeuristicClassifier,
    LlmClassifier,
)
from qaforge_agents.llm.client import LLMClient
from qaforge_agents.llm.providers.base import Provider
from qaforge_agents.llm.providers.mock import MockProvider
from qaforge_agents.llm.recorder import StructLogRecorder
from qaforge_agents.planner import PlannerAgent
from qaforge_agents.ui_tester import UiTesterAgent


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Process-wide LLMClient.

    Phase 1 ships only the mock provider — real providers (Anthropic /
    OpenAI / Gemini) plug in here once API keys are configured. Until
    then, agents that depend on the LLM will produce stubbed plans, and
    tests must inject their own provider via ``dependency_overrides``.
    """
    providers: dict[str, Provider] = {"mock": MockProvider()}
    return LLMClient(
        providers=providers,
        recorder=StructLogRecorder(),
    )


def get_planner_agent() -> PlannerAgent:
    return PlannerAgent(get_llm_client())


def get_api_tester_agent() -> ApiTesterAgent:
    return ApiTesterAgent(get_llm_client())


def get_ui_tester_agent() -> UiTesterAgent:
    return UiTesterAgent(get_llm_client())


def get_failure_classifier_agent() -> FailureClassifierAgent:
    return FailureClassifierAgent(
        llm_classifier=LlmClassifier(get_llm_client()),
        heuristic=HeuristicClassifier(),
    )


def reset_factory_caches() -> None:
    """Test helper."""
    get_llm_client.cache_clear()
