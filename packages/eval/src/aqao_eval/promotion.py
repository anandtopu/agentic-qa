"""Promote feedback regression cases into the scored dataset — TD-007.

``AgentFeedbackService.convert_to_eval_case`` (Epic 6.3) writes
thumbs-down regressions to ``<agent>/feedback_cases.jsonl``, but
:func:`aqao_eval.datasets.load_dataset` only reads the pinned
``<agent>/<version>.jsonl`` — so those cases are written and then never
scored. This module closes that loop: it merges new feedback cases into
the pinned dataset version, idempotently, so the next eval run includes
them.

It deliberately stops there. Re-pinning the regression *baseline* stays
the manual ``set-baseline`` step, so promotion can never silently mask a
regression by moving the bar — it only ever *grows* the scored dataset.

The functions are plain filesystem operations an external scheduler (or
``make eval-promote``) invokes on a cadence — the same "in-process logic,
external cron" shape as the retention sweep and lifecycle alerts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aqao_eval.datasets import load_jsonl
from aqao_eval.feedback_cases import FEEDBACK_DATASET_FILENAME, feedback_dataset_path


@dataclass(slots=True, frozen=True)
class FeedbackPromotionResult:
    """Outcome of promoting one agent's feedback cases."""

    agent_kind: str
    dataset_version: str
    dataset_path: Path
    promoted_case_ids: tuple[str, ...]
    skipped_existing: int
    feedback_case_total: int

    @property
    def promoted_count(self) -> int:
        return len(self.promoted_case_ids)


def _dataset_path(base_dir: Path, agent_kind: str, dataset_version: str) -> Path:
    return base_dir / agent_kind / f"{dataset_version}.jsonl"


def promote_feedback_cases(
    *,
    base_dir: Path,
    agent_kind: str,
    dataset_version: str = "v1",
) -> FeedbackPromotionResult:
    """Merge one agent's feedback cases into its pinned dataset version.

    Idempotent on case id: a case already present in the dataset (or a
    duplicate within the feedback file) is skipped, so re-running promotes
    nothing new. The dataset file is created if it doesn't exist yet, so
    an agent whose only cases are feedback-derived still gets scored.
    """
    feedback_path = feedback_dataset_path(base_dir=base_dir, agent_kind=agent_kind)
    dataset_path = _dataset_path(base_dir, agent_kind, dataset_version)

    feedback_cases = load_jsonl(feedback_path) if feedback_path.is_file() else []
    existing_ids = (
        {case.id for case in load_jsonl(dataset_path)} if dataset_path.is_file() else set()
    )

    to_promote = []
    seen: set[str] = set()
    for case in feedback_cases:
        if case.id in existing_ids or case.id in seen:
            continue
        seen.add(case.id)
        to_promote.append(case)

    if to_promote:
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with dataset_path.open("a", encoding="utf-8") as fp:
            for case in to_promote:
                fp.write(json.dumps(case.model_dump(mode="json"), sort_keys=True))
                fp.write("\n")

    return FeedbackPromotionResult(
        agent_kind=agent_kind,
        dataset_version=dataset_version,
        dataset_path=dataset_path,
        promoted_case_ids=tuple(case.id for case in to_promote),
        skipped_existing=len(feedback_cases) - len(to_promote),
        feedback_case_total=len(feedback_cases),
    )


def promote_all_feedback_cases(
    *,
    base_dir: Path,
    dataset_version: str = "v1",
) -> list[FeedbackPromotionResult]:
    """Promote feedback cases for every agent dir that has a feedback file."""
    if not base_dir.is_dir():
        return []
    results: list[FeedbackPromotionResult] = []
    for agent_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        if (agent_dir / FEEDBACK_DATASET_FILENAME).is_file():
            results.append(
                promote_feedback_cases(
                    base_dir=base_dir,
                    agent_kind=agent_dir.name,
                    dataset_version=dataset_version,
                )
            )
    return results


__all__ = [
    "FeedbackPromotionResult",
    "promote_all_feedback_cases",
    "promote_feedback_cases",
]
