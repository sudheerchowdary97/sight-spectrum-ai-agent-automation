"""Mock ERP FastAPI app. Run with ``uvicorn invoice_agent.mock_erp.main:app``.

Task 0: health only. Task 2 adds:
    GET  /api/v1/purchase-orders/{po_number}
    GET  /api/v1/goods-receipts?po_number=...
    GET  /api/v1/ar-items?status=open
    POST /api/v1/payment-journals
    POST /api/v1/cash-applications
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from invoice_agent import __version__

router = APIRouter(prefix="/api/v1", tags=["erp"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="mock-erp", version=__version__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mock ERP API",
        version=__version__,
        description="Stand-in ERP exposing PO/GR reads and journal posting for the agent.",
    )
    app.include_router(router)
    return app


app = create_app()
