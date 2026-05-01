"""Unit tests for feedback-driven eval-case writer — Epic 6.3."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from aqao_eval.feedback_cases import (
    FEEDBACK_DATASET_FILENAME,
    append_feedback_case,
    build_feedback_case,
    feedback_dataset_path,
    make_case_id,
)


def _build_case(
    *,
    feedback_id: uuid.UUID | None = None,
    agent_kind: str = "classifier",
    inputs: dict | None = None,
    expected: dict | None = None,
    comment: str | None = None,
    redact: callable | None = None,
):
    return build_feedback_case(
        feedback_id=feedback_id or uuid.uuid4(),
        agent_kind=agent_kind,
        resource_type="failure_classification",
        resource_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        submitted_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
        inputs=inputs or {"signal": "AssertionError"},
        expected=expected,
        comment=comment,
        redact=redact,
    )


def test_make_case_id_is_stable(tmp_path: Path) -> None:
    fid = uuid.UUID("11111111-2222-3333-4444-555555555555")
    assert make_case_id(fid) == "feedback-11111111-2222-3333-4444-555555555555"


def test_build_feedback_case_marks_labels_and_metadata() -> None:
    case = _build_case()
    assert "feedback" in case.labels
    assert "regression" in case.labels
    assert case.metadata["source"] == "user_feedback"
    assert case.metadata["agent_kind"] == "classifier"
    assert case.metadata["submitted_at"].endswith("+00:00")


def test_append_feedback_case_creates_dataset_file(tmp_path: Path) -> None:
    case = _build_case(agent_kind="planner")
    result = append_feedback_case(
        base_dir=tmp_path,
        case=case,
        agent_kind="planner",
    )
    assert result.created is True
    assert result.relative_path == f"planner/{FEEDBACK_DATASET_FILENAME}"
    target = tmp_path / "planner" / FEEDBACK_DATASET_FILENAME
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert payload["id"] == case.id


def test_append_feedback_case_is_idempotent_on_id(tmp_path: Path) -> None:
    fid = uuid.uuid4()
    first = append_feedback_case(
        base_dir=tmp_path,
        case=_build_case(feedback_id=fid),
        agent_kind="classifier",
    )
    second = append_feedback_case(
        base_dir=tmp_path,
        case=_build_case(feedback_id=fid),
        agent_kind="classifier",
    )
    assert first.created is True
    assert second.created is False
    assert second.case_id == first.case_id

    target = feedback_dataset_path(base_dir=tmp_path, agent_kind="classifier")
    lines = [
        line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 1


def test_append_feedback_case_appends_distinct_cases(tmp_path: Path) -> None:
    a = append_feedback_case(
        base_dir=tmp_path,
        case=_build_case(),
        agent_kind="classifier",
    )
    b = append_feedback_case(
        base_dir=tmp_path,
        case=_build_case(),
        agent_kind="classifier",
    )
    assert a.created and b.created
    target = feedback_dataset_path(base_dir=tmp_path, agent_kind="classifier")
    lines = [
        line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 2


def test_redactor_scrubs_inputs_expected_and_comment() -> None:
    def _redact(text: str) -> str:
        return text.replace("secret-xyz", "[REDACTED]")

    case = _build_case(
        inputs={"prompt": "leaks secret-xyz", "nested": {"k": "secret-xyz"}},
        expected={"summary": "carries secret-xyz"},
        comment="here: secret-xyz",
        redact=_redact,
    )
    payload = case.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)
    assert "secret-xyz" not in serialized


def test_loader_can_round_trip_appended_case(tmp_path: Path) -> None:
    from aqao_eval.datasets import load_jsonl

    case = _build_case()
    append_feedback_case(base_dir=tmp_path, case=case, agent_kind="classifier")
    target = feedback_dataset_path(base_dir=tmp_path, agent_kind="classifier")
    cases = load_jsonl(target)
    assert len(cases) == 1
    assert cases[0].id == case.id
    assert "feedback" in cases[0].labels
