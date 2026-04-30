"""Prompt template for the API Testing Agent."""

from __future__ import annotations

import json
from typing import Any

from qaforge_agents.api_tester.schema import GeneratedTestSuite

PROMPT_VERSION = "1.0.0"

SYSTEM = """\
You are QAForge AI's API Testing Agent. You convert an OpenAPI requirement
and a test plan into a single self-contained pytest+httpx file.

Hard rules:
1. Output a single JSON object matching the schema.
2. ``source_code`` must be valid Python 3.12. It must:
   - import only `pytest`, `httpx`, and `os` (no other third-party imports);
   - read the base URL from `os.environ["QAFORGE_API_BASE_URL"]`;
   - read auth from `os.environ.get("QAFORGE_API_TOKEN")` and pass as
     `Authorization: Bearer ...` when the test requires auth;
   - define one `test_*` function per test case, with no parametrize loops;
   - assert at minimum the response status code matches the expected status.
3. For negative tests (`is_negative=true`), use deliberately bad inputs and
   assert the appropriate 4xx status.
4. Generate AT LEAST ONE test per provided test_case where the case `type`
   is one of: api, integration, negative, regression, smoke. Skip ui/db.
5. Function names must be unique within the file and match the schema regex.
6. Output JSON only — no Markdown, no prose.
"""


def build_user_prompt(
    *,
    module_name: str,
    openapi_summary: dict[str, Any],
    test_cases: list[dict[str, Any]],
    base_url_default: str | None = None,
) -> str:
    schema_json = json.dumps(
        GeneratedTestSuite.model_json_schema(),
        indent=2,
        sort_keys=True,
    )
    return f"""\
Module name (use this exactly): {module_name}

OpenAPI summary:
{json.dumps(openapi_summary, indent=2)}

Test cases to generate code for:
{json.dumps(test_cases, indent=2)}

Default base URL for documentation only (the code must still read from env): \
{base_url_default or "(none)"}

Output schema:
{schema_json}
"""
