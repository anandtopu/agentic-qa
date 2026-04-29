"""FastAPI application factory.

Phase 0 wires the cross-cutting concerns (config, logging, correlation ID,
health checks) so subsequent phases can plug in routers without revisiting
bootstrap.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from qaforge_api import __version__
from qaforge_api.config import get_settings
from qaforge_api.logging import configure_logging, get_logger
from qaforge_api.middleware import CorrelationIdMiddleware
from qaforge_api.routers import health, workspaces


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("qaforge_api.startup")
    log.info(
        "api.starting",
        env=settings.env,
        version=__version__,
        default_model=settings.default_model,
    )
    try:
        yield
    finally:
        log.info("api.stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QAForge AI API",
        version=__version__,
        description="Agentic software QA platform — Control Plane API (PRD §13).",
        lifespan=_lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(workspaces.router)
    return app


app = create_app()
