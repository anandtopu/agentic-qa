"""Structured JSON logging via structlog.

All logs flow through the redaction processor before serialisation, so
secrets accidentally captured in `extra={...}` are scrubbed.
"""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog
from structlog.types import EventDict, WrappedLogger

from qaforge_redaction import default_redactor


def _redact_processor(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Run the redactor over every string value in the event dict."""
    redactor = default_redactor()
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = redactor.redact(value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Idempotent log setup. Call once at process start."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
