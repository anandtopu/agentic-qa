"""Jinja2-based Markdown renderer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from aqao_agents.reporter.types import RunReportContext

_TEMPLATE_NAME = "run_report.md.j2"


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.isoformat(timespec="seconds")


def _format_duration_ms(ms: int) -> str:
    if ms <= 0:
        return "—"
    if ms < 1000:
        return f"{ms} ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.0f}s"


def _format_cents(cents: int) -> str:
    if cents <= 0:
        return "$0.00"
    return f"${cents / 100:.2f}"


def _format_decimal_pct(value: Decimal) -> str:
    pct = (value * Decimal("100")).quantize(Decimal("0.01"))
    return f"{pct}%"


@dataclass(slots=True)
class MarkdownReportRenderer:
    """Renders a :class:`RunReportContext` as a Markdown string.

    The template lives at ``aqao_agents/reporter/templates/run_report.md.j2``
    and is loaded via Jinja's ``PackageLoader`` so it ships inside the
    wheel.
    """

    template_version: str = "1.0.0"

    def render(self, context: RunReportContext) -> str:
        env = Environment(
            loader=PackageLoader("aqao_agents.reporter", "templates"),
            autoescape=select_autoescape(default=False, default_for_string=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        env.filters["dt"] = _format_dt
        env.filters["duration_ms"] = _format_duration_ms
        env.filters["cents"] = _format_cents
        env.filters["decimal_pct"] = _format_decimal_pct

        template = env.get_template(_TEMPLATE_NAME)
        return template.render(ctx=context)
