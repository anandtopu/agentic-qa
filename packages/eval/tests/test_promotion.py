"""Tests for feedback-case promotion — TD-007.

Promotion is what makes the feedback → eval loop actually close: cases
written by ``convert_to_eval_case`` to ``<agent>/feedback_cases.jsonl``
must land in the pinned ``<agent>/<version>.jsonl`` so the next run
scores them. The contract is: merge new cases, never duplicate, never
touch the baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

from aqao_eval.datasets import load_dataset, load_jsonl
from aqao_eval.feedback_cases import FEEDBACK_DATASET_FILENAME
from aqao_eval.promotion import (
    promote_all_feedback_cases,
    promote_feedback_cases,
)
from aqao_eval.types import EvalCase

_AGENT = "classifier"


def _case(case_id: str) -> EvalCase:
    return EvalCase(id=case_id, inputs={"signal": case_id}, expected={"category": "x"})


def _write_jsonl(path: Path, cases: list[EvalCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for case in cases:
            fp.write(json.dumps(case.model_dump(mode="json"), sort_keys=True) + "\n")


def _feedback_path(base: Path, agent: str) -> Path:
    return base / agent / FEEDBACK_DATASET_FILENAME


def _dataset_path(base: Path, agent: str, version: str = "v1") -> Path:
    return base / agent / f"{version}.jsonl"


# ---------------------------------------------------------------- merge


def test_promote_appends_new_feedback_cases_to_dataset(tmp_path: Path) -> None:
    _write_jsonl(_dataset_path(tmp_path, _AGENT), [_case("base-1")])
    _write_jsonl(_feedback_path(tmp_path, _AGENT), [_case("feedback-abc")])

    result = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)

    assert result.promoted_count == 1
    assert result.promoted_case_ids == ("feedback-abc",)
    assert result.skipped_existing == 0
    # The case is now part of the scored dataset.
    dataset = load_dataset(base_dir=tmp_path, agent=_AGENT, version="v1")
    assert {c.id for c in dataset} == {"base-1", "feedback-abc"}


def test_promote_preserves_existing_dataset_rows(tmp_path: Path) -> None:
    _write_jsonl(
        _dataset_path(tmp_path, _AGENT), [_case("base-1"), _case("base-2")]
    )
    _write_jsonl(_feedback_path(tmp_path, _AGENT), [_case("feedback-1")])
    promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    ids = [c.id for c in load_jsonl(_dataset_path(tmp_path, _AGENT))]
    assert ids == ["base-1", "base-2", "feedback-1"]


# ---------------------------------------------------------------- idempotency


def test_promote_is_idempotent(tmp_path: Path) -> None:
    _write_jsonl(_dataset_path(tmp_path, _AGENT), [_case("base-1")])
    _write_jsonl(_feedback_path(tmp_path, _AGENT), [_case("feedback-1")])

    first = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    second = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)

    assert first.promoted_count == 1
    assert second.promoted_count == 0
    assert second.skipped_existing == 1
    # No duplicate line for the promoted case.
    ids = [c.id for c in load_jsonl(_dataset_path(tmp_path, _AGENT))]
    assert ids.count("feedback-1") == 1


def test_promote_skips_case_already_in_dataset(tmp_path: Path) -> None:
    _write_jsonl(_dataset_path(tmp_path, _AGENT), [_case("dup-1")])
    _write_jsonl(_feedback_path(tmp_path, _AGENT), [_case("dup-1"), _case("new-1")])

    result = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    assert result.promoted_case_ids == ("new-1",)
    assert result.skipped_existing == 1


# ---------------------------------------------------------------- edge cases


def test_promote_creates_dataset_when_missing(tmp_path: Path) -> None:
    # Only the feedback file exists — no pinned dataset yet.
    _write_jsonl(_feedback_path(tmp_path, _AGENT), [_case("feedback-1")])
    result = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    assert result.promoted_count == 1
    assert _dataset_path(tmp_path, _AGENT).is_file()
    assert {c.id for c in load_dataset(base_dir=tmp_path, agent=_AGENT, version="v1")} == {
        "feedback-1"
    }


def test_promote_no_feedback_file_is_noop(tmp_path: Path) -> None:
    _write_jsonl(_dataset_path(tmp_path, _AGENT), [_case("base-1")])
    result = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    assert result.promoted_count == 0
    assert result.feedback_case_total == 0


def test_promote_dedupes_within_feedback_file(tmp_path: Path) -> None:
    _write_jsonl(
        _feedback_path(tmp_path, _AGENT), [_case("feedback-1"), _case("feedback-1")]
    )
    result = promote_feedback_cases(base_dir=tmp_path, agent_kind=_AGENT)
    assert result.promoted_count == 1
    ids = [c.id for c in load_jsonl(_dataset_path(tmp_path, _AGENT))]
    assert ids == ["feedback-1"]


# ---------------------------------------------------------------- multi-agent


def test_promote_all_iterates_every_agent_with_feedback(tmp_path: Path) -> None:
    _write_jsonl(_feedback_path(tmp_path, "classifier"), [_case("c-1")])
    _write_jsonl(_feedback_path(tmp_path, "planner"), [_case("p-1"), _case("p-2")])
    # An agent dir with only a dataset (no feedback) is left alone.
    _write_jsonl(_dataset_path(tmp_path, "reporter"), [_case("r-1")])

    results = promote_all_feedback_cases(base_dir=tmp_path)
    by_agent = {r.agent_kind: r for r in results}

    assert set(by_agent) == {"classifier", "planner"}
    assert by_agent["classifier"].promoted_count == 1
    assert by_agent["planner"].promoted_count == 2


def test_promote_all_missing_base_dir_is_empty(tmp_path: Path) -> None:
    assert promote_all_feedback_cases(base_dir=tmp_path / "nope") == []
