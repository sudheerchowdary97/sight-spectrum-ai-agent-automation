"""Health & readiness endpoints (GET /api/v1/health)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from invoice_agent import __version__
from invoice_agent.config import get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Return service liveness. Extended with dependency checks in later tasks."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )
