"""Liveness and readiness endpoints.

`/healthz` is liveness — the process is alive. `/readyz` is readiness —
all required dependencies (DB, Redis) are reachable. Liveness must never
depend on anything external; readiness is what should gate traffic.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel

from qaforge_api import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/healthz", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe. Always returns 200 if the process is up."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/readyz", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Readiness probe. Phase 0 stub — Phase 1 will check DB and Redis."""
    return HealthResponse(status="ok", version=__version__)
