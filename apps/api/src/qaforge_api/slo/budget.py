"""Error budget + freeze-policy — Epic 4.1.

PRD AC: "SLOs visible in Grafana; breach triggers freeze policy."
This module is the policy half — given an :class:`ErrorBudget`
snapshot, decide whether to freeze deploys / non-critical work.

The freeze policy is intentionally simple: when ``remaining_fraction``
crosses below configurable thresholds, we emit progressively-louder
:class:`FreezeDecision` outcomes. A deploy gate / on-call workflow
consumes the decision; this package does not take a position on
*how* a freeze is enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from qaforge_api.slo.types import Slo


@dataclass(slots=True, frozen=True)
class ErrorBudget:
    """Snapshot of the error budget for one :class:`Slo`.

    ``allowed_bad_fraction`` is ``1 - objective`` — the fraction of
    samples we're allowed to fail. ``consumed_fraction`` is how much
    of that budget we've actually burned. ``remaining_fraction`` is
    ``1 - consumed/allowed`` clamped to ``[0, 1]``.
    """

    slo_name: str
    allowed_bad_fraction: float
    consumed_fraction: float
    remaining_fraction: float

    @classmethod
    def from_compliance(cls, *, slo: Slo, compliance: float) -> ErrorBudget:
        allowed = 1.0 - slo.objective
        observed_bad = max(0.0, 1.0 - compliance)
        if allowed <= 0.0:  # pragma: no cover - rejected by Slo validator
            consumed = 0.0
            remaining = 1.0
        else:
            consumed = min(observed_bad / allowed, 1.0)
            remaining = max(0.0, 1.0 - consumed)
        return cls(
            slo_name=slo.name,
            allowed_bad_fraction=allowed,
            consumed_fraction=consumed,
            remaining_fraction=remaining,
        )

    @property
    def exhausted(self) -> bool:
        return self.remaining_fraction <= 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_name": self.slo_name,
            "allowed_bad_fraction": self.allowed_bad_fraction,
            "consumed_fraction": self.consumed_fraction,
            "remaining_fraction": self.remaining_fraction,
            "exhausted": self.exhausted,
        }


class FreezeLevel(StrEnum):
    """Escalating freeze states."""

    NORMAL = "normal"  # > warn threshold remaining
    WATCH = "watch"  # below warn, above freeze threshold
    SOFT_FREEZE = "soft_freeze"  # below freeze threshold, budget left
    HARD_FREEZE = "hard_freeze"  # budget exhausted


@dataclass(slots=True, frozen=True)
class FreezeDecision:
    """What the freeze policy says about one SLO right now."""

    slo_name: str
    level: FreezeLevel
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_name": self.slo_name,
            "level": self.level.value,
            "reason": self.reason,
        }


@dataclass(slots=True)
class FreezePolicy:
    """Map a windowed :class:`ErrorBudget` to a :class:`FreezeDecision`.

    Defaults: WATCH at <50% remaining, SOFT_FREEZE at <25%, HARD_FREEZE
    at 0%. Tuneable per SLO via the constructor; the same numbers cover
    every PRD §14.5 surface in practice.
    """

    warn_threshold: float = 0.50
    freeze_threshold: float = 0.25

    def __post_init__(self) -> None:
        if not (0.0 < self.freeze_threshold < self.warn_threshold < 1.0):
            raise ValueError(
                "thresholds must satisfy 0 < freeze < warn < 1; got "
                f"freeze={self.freeze_threshold}, warn={self.warn_threshold}"
            )

    def decide(self, budget: ErrorBudget) -> FreezeDecision:
        if budget.exhausted:
            return FreezeDecision(
                slo_name=budget.slo_name,
                level=FreezeLevel.HARD_FREEZE,
                reason=(
                    "error budget exhausted — block all non-critical "
                    "deploys until the burn rate cools"
                ),
            )
        if budget.remaining_fraction < self.freeze_threshold:
            return FreezeDecision(
                slo_name=budget.slo_name,
                level=FreezeLevel.SOFT_FREEZE,
                reason=(
                    f"only {budget.remaining_fraction:.0%} of the budget "
                    "remains — pause non-essential changes"
                ),
            )
        if budget.remaining_fraction < self.warn_threshold:
            return FreezeDecision(
                slo_name=budget.slo_name,
                level=FreezeLevel.WATCH,
                reason=(
                    f"budget at {budget.remaining_fraction:.0%} — investigate "
                    "the burn rate before it crosses the freeze line"
                ),
            )
        return FreezeDecision(
            slo_name=budget.slo_name,
            level=FreezeLevel.NORMAL,
            reason=f"budget healthy ({budget.remaining_fraction:.0%} remaining)",
        )


__all__ = ["ErrorBudget", "FreezeDecision", "FreezeLevel", "FreezePolicy"]
