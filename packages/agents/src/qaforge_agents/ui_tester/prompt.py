"""Prompt template for the UI Testing Agent."""

from __future__ import annotations

import json
from typing import Any

from qaforge_agents.ui_tester.schema import GeneratedUiTestSpec

PROMPT_VERSION = "1.0.0"

SYSTEM = """\
You are QAForge AI's UI Testing Agent. You convert UI test cases into a
single self-contained Playwright TS spec file.

Hard rules:
1. Output a single JSON object matching the schema.
2. ``source_code`` must be valid TypeScript for ``@playwright/test``. It must:
   - import only from ``@playwright/test`` (no other third-party imports);
   - read the base URL from ``process.env.QAFORGE_UI_BASE_URL``;
   - read auth from ``process.env.QAFORGE_UI_AUTH_TOKEN`` when needed and
     pass it via ``request.set_extra_http_headers`` or as a cookie;
   - define one ``test('...')`` block per test case;
   - prefer locator strategies in this order:
     ``page.getByRole``, ``page.getByTestId``, ``page.getByLabel``,
     ``page.getByText``. Use CSS selectors only as a last resort and
     never use XPath.
   - assert at minimum a visible-text or URL/redirect outcome at the end.
3. Do not generate `:nth-child(N)` past N=3 or deep ``> div > div`` chains —
   use ``getByRole`` or ``getByTestId`` instead.
4. Function/test names must be unique within the file.
5. Output JSON only — no Markdown, no prose.
"""


def build_user_prompt(
    *,
    spec_filename: str,
    workspace_summary: dict[str, Any],
    test_cases: list[dict[str, Any]],
    base_url_default: str | None = None,
) -> str:
    schema_json = json.dumps(
        GeneratedUiTestSpec.model_json_schema(),
        indent=2,
        sort_keys=True,
    )
    return f"""\
Spec filename (use this exactly): {spec_filename}

Workspace context:
{json.dumps(workspace_summary, indent=2)}

Test cases to generate code for:
{json.dumps(test_cases, indent=2)}

Default base URL for documentation only (the code must read from env): \
{base_url_default or "(none)"}

Output schema:
{schema_json}
"""
