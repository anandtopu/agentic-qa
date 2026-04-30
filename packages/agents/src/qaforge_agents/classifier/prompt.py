"""Prompt template for the LLM failure classifier."""

from __future__ import annotations

import json
from typing import Any

from qaforge_agents.classifier.schema import FailureSignal

PROMPT_VERSION = "1.0.0"

SYSTEM = """\
You are QAForge AI's Failure Classifier. You receive a single failure
signal from a test run and produce a structured classification.

Hard rules:
1. Output a single JSON object matching the schema you are given.
2. ``category`` is exactly one of:
   - ``product_defect``  — the system-under-test misbehaved.
   - ``test_issue``       — the test itself is wrong (bad selector, stale
                            assertion, hard-coded data).
   - ``environment_issue`` — infrastructure or transport problem
                             (DNS, timeouts, expired creds, rate limits).
   - ``flaky_test``       — non-deterministic; retry would likely pass.
   - ``data_issue``       — test data missing or stale.
   - ``unknown``          — insufficient evidence to classify.
3. ``confidence`` is a decimal in [0, 1]. Calibrate honestly: 0.9+
   only when the evidence is unambiguous; 0.5 or lower when you're
   guessing.
4. ``reasoning`` is one or two short sentences pointing at the specific
   evidence you used.
5. ``suggested_fix`` is optional but encouraged when the category is
   actionable.
6. Output JSON only — no Markdown, no prose.
"""


def build_user_prompt(*, signal: FailureSignal, response_schema_json: str) -> str:
    snapshot: dict[str, Any] = {
        "signal_id": signal.signal_id,
        "test_name": signal.test_name,
        "agent_name": signal.agent_name,
        "tool": signal.tool,
        "http_status_code": signal.http_status_code,
        "duration_ms": signal.duration_ms,
        "error_message": signal.error_message,
        "stdout_excerpt": signal.stdout_excerpt,
        "stderr_excerpt": signal.stderr_excerpt,
        "metadata": signal.metadata,
    }
    return f"""\
Classify this failure signal:

{json.dumps(snapshot, indent=2)}

Output schema:
{response_schema_json}
"""
