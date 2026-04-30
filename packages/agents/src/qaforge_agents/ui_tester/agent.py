"""UiTesterAgent — generates Playwright TS specs from UI test cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from qaforge_agents.llm.client import LLMClient, StructuredOutputError
from qaforge_agents.llm.types import LLMRequest, Message, Role, Tier, UsageRecord
from qaforge_agents.ui_tester.prompt import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_prompt,
)
from qaforge_agents.ui_tester.schema import GeneratedUiTestSpec
from qaforge_agents.ui_tester.selector_analysis import (
    FragilityReport,
    analyse_selectors,
)
from qaforge_agents.ui_tester.ts_validator import (
    GeneratedSpecInvalid,
    validate_spec,
)

_UI_TEST_TYPES = frozenset({"ui", "smoke", "regression", "integration"})


@dataclass(slots=True)
class UiTesterInput:
    test_plan_id: UUID
    workspace_id: UUID | None
    spec_filename: str
    workspace_summary: dict[str, Any]
    test_cases: list[dict[str, Any]]
    base_url_default: str | None = None
    correlation_id: str | None = None


@dataclass(slots=True)
class UiTesterOutput:
    spec: GeneratedUiTestSpec
    fragility_report: FragilityReport
    usage: UsageRecord
    prompt_version: str = field(default=PROMPT_VERSION)


class UiTesterAgent:
    def __init__(self, llm: LLMClient, *, tier: Tier = Tier.MID) -> None:
        self._llm = llm
        self._tier = tier

    @staticmethod
    def filter_relevant_cases(
        test_cases: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep UI/smoke/regression/integration cases; drop pure API/DB."""
        return [case for case in test_cases if str(case.get("type", "")).lower() in _UI_TEST_TYPES]

    async def generate(self, inputs: UiTesterInput) -> UiTesterOutput:
        relevant = self.filter_relevant_cases(inputs.test_cases)
        if not relevant:
            raise StructuredOutputError(
                "no UI-tier test cases to generate (none had ui/smoke/regression/integration type)"
            )

        request = LLMRequest(
            messages=[
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(
                    role=Role.USER,
                    content=build_user_prompt(
                        spec_filename=inputs.spec_filename,
                        workspace_summary=inputs.workspace_summary,
                        test_cases=relevant,
                        base_url_default=inputs.base_url_default,
                    ),
                ),
            ],
            tier=self._tier,
            response_schema=GeneratedUiTestSpec,
            workspace_id=inputs.workspace_id,
            correlation_id=inputs.correlation_id,
            metadata={
                "agent": "ui_tester",
                "prompt_version": PROMPT_VERSION,
                "test_plan_id": str(inputs.test_plan_id),
            },
        )

        response = await self._llm.complete(request)
        if not isinstance(response.structured, GeneratedUiTestSpec):
            raise StructuredOutputError("ui-tester LLM response was not a GeneratedUiTestSpec")
        spec: GeneratedUiTestSpec = response.structured

        try:
            validate_spec(spec.source_code)
        except GeneratedSpecInvalid:
            raise

        report = analyse_selectors(spec.source_code)
        return UiTesterOutput(
            spec=spec,
            fragility_report=report,
            usage=response.usage,
        )
