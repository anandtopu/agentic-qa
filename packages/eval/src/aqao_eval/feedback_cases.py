"""Feedback-driven regression case writer — Epic 6.3.

When the platform receives a thumbs-down on an agent output, the
weekly review ritual converts it into a regression case under
``packages/eval/datasets/<agent>/feedback_cases.jsonl``. The next
``make eval`` run scores the agent against the same input that
produced the unhappy output, so a fix can be evaluated objectively
and a future regression is caught.

Design notes:

* Cases are appended, never rewritten in place. JSONL is the same
  format the rest of the harness consumes via ``load_jsonl``.
* Case IDs are derived from the feedback row UUID so the writer is
  idempotent — calling it twice for the same feedback is a no-op
  (the second call detects the existing line and returns it
  unchanged).
* The writer never includes raw model outputs verbatim if a
  ``redact`` callable is provided — secret-redaction is a Phase-0
  global invariant (Story 0.4.3).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from aqao_eval.types import EvalCase

FEEDBACK_DATASET_FILENAME = "feedback_cases.jsonl"

Redactor = Callable[[str], str]


@dataclass(slots=True, frozen=True)
class FeedbackCaseAppendResult:
    """Outcome of :func:`append_feedback_case`."""

    case_id: str
    relative_path: str
    absolute_path: Path
    created: bool
    """True when a new line was appended; False when the case was already present."""


def make_case_id(feedback_id: UUID) -> str:
    """Stable case id derived from the feedback row id."""
    return f"feedback-{feedback_id}"


def _normalise_payload(value: Any, redact: Redactor | None) -> Any:
    if redact is None:
        return value
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _normalise_payload(v, redact) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise_payload(v, redact) for v in value]
    return value


def build_feedback_case(
    *,
    feedback_id: UUID,
    agent_kind: str,
    resource_type: str,
    resource_id: UUID,
    workspace_id: UUID,
    submitted_at: datetime,
    inputs: dict[str, Any],
    expected: dict[str, Any] | None = None,
    comment: str | None = None,
    redact: Redactor | None = None,
) -> EvalCase:
    """Build the :class:`EvalCase` row that represents one feedback signal.

    ``inputs`` is the original prompt context the agent saw — the
    snapshot lives next to the case so re-running the eval reproduces
    the failure mode exactly. ``expected`` is the operator's answer
    to "what *should* the agent have done" — populate it as the
    triage outcome lands; an empty mapping is acceptable for the
    initial append.
    """
    case_id = make_case_id(feedback_id)
    metadata: dict[str, Any] = {
        "source": "user_feedback",
        "agent_kind": agent_kind,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
        "workspace_id": str(workspace_id),
        "submitted_at": submitted_at.astimezone(UTC).isoformat(),
    }
    if comment is not None:
        metadata["comment"] = redact(comment) if redact else comment
    return EvalCase(
        id=case_id,
        inputs=_normalise_payload(inputs, redact),
        expected=_normalise_payload(expected or {}, redact),
        labels=["feedback", "regression"],
        metadata=metadata,
    )


def feedback_dataset_path(*, base_dir: Path, agent_kind: str) -> Path:
    return base_dir / agent_kind / FEEDBACK_DATASET_FILENAME


def _existing_case_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            case_id = row.get("id")
            if isinstance(case_id, str):
                ids.add(case_id)
    return ids


def append_feedback_case(
    *,
    base_dir: Path,
    case: EvalCase,
    agent_kind: str,
) -> FeedbackCaseAppendResult:
    """Append ``case`` as a new JSONL line under the agent's feedback file.

    Idempotent on case id: if the case is already present, no write
    happens and ``created=False`` is returned.
    """
    dataset_path = feedback_dataset_path(base_dir=base_dir, agent_kind=agent_kind)
    relative = f"{agent_kind}/{FEEDBACK_DATASET_FILENAME}"
    if case.id in _existing_case_ids(dataset_path):
        return FeedbackCaseAppendResult(
            case_id=case.id,
            relative_path=relative,
            absolute_path=dataset_path,
            created=False,
        )
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    payload = case.model_dump(mode="json")
    with dataset_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, sort_keys=True))
        fp.write("\n")
    return FeedbackCaseAppendResult(
        case_id=case.id,
        relative_path=relative,
        absolute_path=dataset_path,
        created=True,
    )


__all__ = [
    "FEEDBACK_DATASET_FILENAME",
    "FeedbackCaseAppendResult",
    "append_feedback_case",
    "build_feedback_case",
    "feedback_dataset_path",
    "make_case_id",
]
