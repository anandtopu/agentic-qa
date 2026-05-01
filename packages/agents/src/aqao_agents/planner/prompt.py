"""Prompt template for the Planner agent.

Versioned — when we change the prompt, bump :data:`PROMPT_VERSION` so
historical eval scorecards stay comparable.
"""

from __future__ import annotations

import json
from typing import Any

from aqao_agents.planner.schema import PlannerTestPlan

PROMPT_VERSION = "1.0.0"

SYSTEM = """\
You are Agentic QA Orchestrator's Planner Agent. Your job is to turn an ingested
requirement into a high-quality structured test plan.

Hard rules:
1. Produce a single JSON object that matches the schema you are given.
2. Generate AT LEAST ONE test case for every acceptance criterion.
3. Mix test types: API, UI, DB, integration, negative, regression, smoke
   — pick what the requirement actually warrants. Do not add UI tests
   if the requirement is purely backend.
4. Mark a case `automation_candidate=false` only when the steps require
   visual judgement, exploratory reasoning, or external systems Agentic QA Orchestrator
   cannot drive.
5. If anything is ambiguous or under-specified, add it to
   `open_questions`. It is better to flag than to invent.
6. Be specific — vague titles like "Test login" are rejected.
7. Output JSON only. No prose, no Markdown fences.
"""


def build_user_prompt(
    *,
    requirement_summary: str,
    requirement_type: str,
    parsed_payload: dict[str, Any],
    workspace_context: dict[str, Any] | None = None,
    existing_test_titles: list[str] | None = None,
) -> str:
    schema_json = json.dumps(
        PlannerTestPlan.model_json_schema(),
        indent=2,
        sort_keys=True,
    )
    workspace_block = (
        f"\nWorkspace context:\n{json.dumps(workspace_context, indent=2)}"
        if workspace_context
        else ""
    )
    existing_block = (
        "\nExisting test titles in this workspace (avoid duplicating these):\n- "
        + "\n- ".join(existing_test_titles)
        if existing_test_titles
        else ""
    )

    return f"""\
Requirement type: {requirement_type}
Requirement summary: {requirement_summary}

Parsed requirement payload (authoritative):
{json.dumps(parsed_payload, indent=2)}
{workspace_block}{existing_block}

Output a JSON object matching this schema. Field-level constraints
(min/max length, enums, required) are enforced at validation time.

Schema:
{schema_json}
"""
