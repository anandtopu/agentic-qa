"""PlannerAgent — calls the LLM and returns a validated test plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from aqao_agents.llm.client import LLMClient
from aqao_agents.llm.types import LLMRequest, Message, Role, Tier, UsageRecord
from aqao_agents.planner.ambiguity import detect_open_questions
from aqao_agents.planner.prompt import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_prompt,
)
from aqao_agents.planner.schema import PlannerTestPlan


@dataclass(slots=True)
class PlannerInput:
    """Everything the Planner needs to make a plan, free of API types."""

    requirement_id: UUID
    requirement_type: str
    requirement_summary: str
    parsed_payload: dict[str, Any]
    workspace_context: dict[str, Any] | None = None
    existing_test_titles: list[str] = field(default_factory=list)
    correlation_id: str | None = None
    workspace_id: UUID | None = None


@dataclass(slots=True)
class PlannerOutput:
    plan: PlannerTestPlan
    usage: UsageRecord
    prompt_version: str


class _PlanWithSchema(BaseModel):
    """Wrapper to make the LLM client validate against the test-plan schema."""

    summary: str
    coverage_areas: list[str]
    test_cases: list[dict[str, Any]]
    open_questions: list[str]


class PlannerAgent:
    """Generates a :class:`PlannerTestPlan` for a requirement.

    Pure business object: takes an :class:`LLMClient` plus inputs and
    returns the validated plan. Side effects (DB persistence, audit) live
    in the API service layer.
    """

    def __init__(
        self,
        llm: LLMClient,
        *,
        tier: Tier = Tier.HIGH,
    ) -> None:
        self._llm = llm
        self._tier = tier

    async def plan(self, inputs: PlannerInput) -> PlannerOutput:
        request = LLMRequest(
            messages=[
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(
                    role=Role.USER,
                    content=build_user_prompt(
                        requirement_summary=inputs.requirement_summary,
                        requirement_type=inputs.requirement_type,
                        parsed_payload=inputs.parsed_payload,
                        workspace_context=inputs.workspace_context,
                        existing_test_titles=inputs.existing_test_titles,
                    ),
                ),
            ],
            tier=self._tier,
            response_schema=PlannerTestPlan,
            workspace_id=inputs.workspace_id,
            correlation_id=inputs.correlation_id,
            metadata={"agent": "planner", "prompt_version": PROMPT_VERSION},
        )

        response = await self._llm.complete(request)
        if not isinstance(response.structured, PlannerTestPlan):
            from aqao_agents.llm.client import StructuredOutputError

            raise StructuredOutputError("planner LLM response was not a PlannerTestPlan instance")
        plan: PlannerTestPlan = response.structured

        # Layer the heuristic ambiguity detector on top of any open questions
        # the model already produced; dedupe while preserving order.
        heuristic = detect_open_questions(
            requirement_summary=inputs.requirement_summary,
            parsed_payload=inputs.parsed_payload,
            test_cases=[tc.model_dump() for tc in plan.test_cases],
        )
        merged = list(plan.open_questions)
        seen = {q.lower() for q in merged}
        for question in heuristic:
            key = question.lower()
            if key not in seen:
                merged.append(question)
                seen.add(key)

        if merged != plan.open_questions:
            plan = plan.model_copy(update={"open_questions": merged})

        return PlannerOutput(
            plan=plan,
            usage=response.usage,
            prompt_version=PROMPT_VERSION,
        )
