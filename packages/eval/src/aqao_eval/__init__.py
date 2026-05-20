"""Agentic QA Orchestrator agent evaluation harness — Epic 2.6.

Per ADR-0010, the harness is custom Python (no LangSmith / Promptfoo
dependency) so we own the rubric and provenance. Public surface:

* :class:`EvalCase`, :class:`Scorecard`, :class:`DimensionAggregate` —
  the wire types every scorer + runner produces.
* :class:`Scorer` Protocol + the built-in scorers under :mod:`aqao_eval.scorers`.
* :class:`EvalRunner` — runs a dataset x agent x scorers combo.
* :class:`BaselineGate` — diffs a fresh scorecard against a pinned
  baseline and reports per-dimension regressions (Story 2.6.3).
"""

from aqao_eval.datasets import EvalDataset, load_dataset, load_jsonl
from aqao_eval.feedback_cases import (
    FEEDBACK_DATASET_FILENAME,
    FeedbackCaseAppendResult,
    append_feedback_case,
    build_feedback_case,
    feedback_dataset_path,
    make_case_id,
)
from aqao_eval.gate import BaselineGate, GateReport, RegressionFinding
from aqao_eval.nightly import (
    NightlyAgentResult,
    NightlyReport,
    NightlyRunner,
    NightlyTarget,
    run_nightly,
)
from aqao_eval.promotion import (
    FeedbackPromotionResult,
    promote_all_feedback_cases,
    promote_feedback_cases,
)
from aqao_eval.runner import AgentInvocation, EvalRunner
from aqao_eval.scorers import (
    CategoricalAccuracyScorer,
    CostBudgetScorer,
    FieldExactMatchScorer,
    JsonSchemaValidScorer,
    LatencyBudgetScorer,
    Scorer,
)
from aqao_eval.trend import (
    AlertSink,
    FilesystemTrendStore,
    LogAlertSink,
    RegressionAlert,
    RegressionAlertEmitter,
    TrendEntry,
    TrendStore,
)
from aqao_eval.types import (
    DimensionAggregate,
    EvalCase,
    Scorecard,
    ScoreResult,
)

__all__ = [
    "FEEDBACK_DATASET_FILENAME",
    "AgentInvocation",
    "AlertSink",
    "BaselineGate",
    "CategoricalAccuracyScorer",
    "CostBudgetScorer",
    "DimensionAggregate",
    "EvalCase",
    "EvalDataset",
    "EvalRunner",
    "FeedbackCaseAppendResult",
    "FeedbackPromotionResult",
    "FieldExactMatchScorer",
    "FilesystemTrendStore",
    "GateReport",
    "JsonSchemaValidScorer",
    "LatencyBudgetScorer",
    "LogAlertSink",
    "NightlyAgentResult",
    "NightlyReport",
    "NightlyRunner",
    "NightlyTarget",
    "RegressionAlert",
    "RegressionAlertEmitter",
    "RegressionFinding",
    "ScoreResult",
    "Scorecard",
    "Scorer",
    "TrendEntry",
    "TrendStore",
    "append_feedback_case",
    "build_feedback_case",
    "feedback_dataset_path",
    "load_dataset",
    "load_jsonl",
    "make_case_id",
    "promote_all_feedback_cases",
    "promote_feedback_cases",
    "run_nightly",
]
