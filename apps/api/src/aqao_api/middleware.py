"""HTTP middlewares: correlation ID, request logging.

Every request gets an ``x-aqao-trace-id`` header (echoed back, generated
if absent). Story 0.4.1 requires that this ID surfaces in logs and traces
so a user-visible request can be followed through the full agent stack.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

TRACE_HEADER = "x-aqao-trace-id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get(TRACE_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            structlog.get_logger().exception("request.failed")
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[TRACE_HEADER] = trace_id
        structlog.get_logger().info(
            "request.completed",
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        return response
