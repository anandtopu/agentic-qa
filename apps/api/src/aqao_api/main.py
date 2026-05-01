"""FastAPI application factory.

Phase 0 wires the cross-cutting concerns (config, logging, correlation ID,
health checks) so subsequent phases can plug in routers without revisiting
bootstrap.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aqao_api import __version__
from aqao_api.config import get_settings
from aqao_api.logging import configure_logging, get_logger
from aqao_api.middleware import CorrelationIdMiddleware
from aqao_api.routers import (
    agent_feedback,
    api_tests,
    approvals,
    audit,
    compliance,
    environments,
    failures,
    flakiness,
    health,
    model_registry,
    policies,
    pr_comment,
    reports,
    repositories,
    requirements,
    test_plans,
    test_runs,
    ui_tests,
    usage,
    webhooks,
    workspaces,
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("aqao_api.startup")
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
        title="Agentic QA Orchestrator API",
        version=__version__,
        description="Agentic software QA platform — Control Plane API (PRD §13).",
        lifespan=_lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(workspaces.router)
    app.include_router(repositories.router)
    app.include_router(environments.router)
    app.include_router(policies.router)
    app.include_router(requirements.per_workspace)
    app.include_router(requirements.flat)
    app.include_router(test_plans.flat)
    app.include_router(test_plans.per_workspace)
    app.include_router(api_tests.router)
    app.include_router(ui_tests.router)
    app.include_router(test_runs.flat)
    app.include_router(test_runs.per_workspace)
    app.include_router(failures.router)
    app.include_router(flakiness.router)
    app.include_router(reports.router)
    app.include_router(pr_comment.router)
    app.include_router(audit.router)
    app.include_router(usage.router)
    app.include_router(approvals.router)
    app.include_router(agent_feedback.router)
    app.include_router(model_registry.router)
    app.include_router(compliance.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
