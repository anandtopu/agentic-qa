"""ApiTesterAgent — generates pytest+httpx code from an OpenAPI requirement."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from qaforge_agents.api_tester.prompt import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_prompt,
)
from qaforge_agents.api_tester.schema import GeneratedTestSuite
from qaforge_agents.llm.client import LLMClient, StructuredOutputError
from qaforge_agents.llm.types import LLMRequest, Message, Role, Tier, UsageRecord

_API_TEST_TYPES = frozenset({"api", "integration", "negative", "regression", "smoke"})


@dataclass(slots=True)
class ApiTesterInput:
    test_plan_id: UUID
    workspace_id: UUID | None
    module_name: str
    openapi_summary: dict[str, Any]
    test_cases: list[dict[str, Any]]
    base_url_default: str | None = None
    correlation_id: str | None = None


@dataclass(slots=True)
class ApiTesterOutput:
    suite: GeneratedTestSuite
    usage: UsageRecord
    prompt_version: str = field(default=PROMPT_VERSION)


class GeneratedCodeInvalid(StructuredOutputError):  # noqa: N818 - public name predates rule
    """Raised when the LLM returns Python that fails to parse."""


class ApiTesterAgent:
    def __init__(self, llm: LLMClient, *, tier: Tier = Tier.MID) -> None:
        self._llm = llm
        self._tier = tier

    @staticmethod
    def filter_relevant_cases(
        test_cases: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Drop UI/DB cases — this agent only generates HTTP-level tests."""
        return [case for case in test_cases if str(case.get("type", "")).lower() in _API_TEST_TYPES]

    async def generate(self, inputs: ApiTesterInput) -> ApiTesterOutput:
        relevant = self.filter_relevant_cases(inputs.test_cases)
        if not relevant:
            raise StructuredOutputError("no API-tier test cases to generate (all cases were UI/DB)")

        request = LLMRequest(
            messages=[
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(
                    role=Role.USER,
                    content=build_user_prompt(
                        module_name=inputs.module_name,
                        openapi_summary=inputs.openapi_summary,
                        test_cases=relevant,
                        base_url_default=inputs.base_url_default,
                    ),
                ),
            ],
            tier=self._tier,
            response_schema=GeneratedTestSuite,
            workspace_id=inputs.workspace_id,
            correlation_id=inputs.correlation_id,
            metadata={
                "agent": "api_tester",
                "prompt_version": PROMPT_VERSION,
                "test_plan_id": str(inputs.test_plan_id),
            },
        )

        response = await self._llm.complete(request)
        if not isinstance(response.structured, GeneratedTestSuite):
            raise StructuredOutputError("api-tester LLM response was not a GeneratedTestSuite")
        suite: GeneratedTestSuite = response.structured

        try:
            ast.parse(suite.source_code)
        except SyntaxError as exc:
            raise GeneratedCodeInvalid(
                f"generated source has a syntax error at line {exc.lineno}: {exc.msg}"
            ) from exc

        return ApiTesterOutput(suite=suite, usage=response.usage)
