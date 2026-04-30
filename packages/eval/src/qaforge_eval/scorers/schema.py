"""JSON-schema validation scorer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from qaforge_eval.types import EvalCase, ScoreResult


@dataclass(slots=True)
class JsonSchemaValidScorer:
    """1.0 iff ``output`` validates against the given Pydantic model.

    Used for agents that emit structured outputs — Planner, ApiTester,
    UiTester all have Pydantic schemas this scorer can consume.
    """

    schema: type[BaseModel]
    dimension: str = "json_schema_valid"

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult:
        try:
            self.schema.model_validate(output)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            return ScoreResult(
                case_id=case.id,
                dimension=self.dimension,
                score=0.0,
                rationale=f"{len(errors)} validation error(s)",
                metadata={"errors": [str(e) for e in errors[:5]]},
            )
        return ScoreResult(
            case_id=case.id,
            dimension=self.dimension,
            score=1.0,
            rationale="output matches schema",
        )
