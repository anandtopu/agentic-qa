"""PageNotifier Protocol + log-only reference impl — Epic 4.2.

Real PagerDuty / Opsgenie / Slack-incident transports are wired by
satisfying the :class:`PageNotifier` Protocol. The Phase-4 default is
a structured-log transport so the contract is testable without
external services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from aqao_api.incident.router import RoutingDecision


@dataclass(slots=True, frozen=True)
class PageDecision:
    """Result of dispatching a page — what was sent, where, and when."""

    decision: RoutingDecision
    delivered_to: tuple[str, ...]
    transport: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "delivered_to": list(self.delivered_to),
            "decision": self.decision.to_dict(),
        }


class PageNotifier(Protocol):
    """The seam every page transport implements."""

    transport: str

    def page(self, decision: RoutingDecision) -> PageDecision: ...


@dataclass(slots=True)
class LogPageNotifier:
    """Reference notifier — emits a structured log per page.

    Logs at WARNING for SEV3+ and ERROR for SEV1/SEV2 so a log-based
    aggregator (Datadog, Cloud Logging) can route on level alone
    while a real PagerDuty integration is in flight.
    """

    transport: str = "structured-log"
    logger: Any | None = None

    def page(self, decision: RoutingDecision) -> PageDecision:
        log = self.logger or structlog.get_logger("aqao_api.incident")
        method = log.error if decision.severity.value in {"SEV1", "SEV2"} else log.warning
        method("incident.page", **decision.to_dict())
        return PageDecision(
            decision=decision,
            delivered_to=tuple(decision.rule.page_channels),
            transport=self.transport,
        )


__all__ = ["LogPageNotifier", "PageDecision", "PageNotifier"]
