"""AR remittance endpoint (POST /api/v1/apply-remittance)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from invoice_agent.ar.models import RemittanceResult
from invoice_agent.ar.service import RemittanceService
from invoice_agent.schemas import Remittance

router = APIRouter(tags=["accounts-receivable"])


def get_remittance_service(request: Request) -> RemittanceService:
    return request.app.state.remittance_service


@router.post(
    "/apply-remittance",
    response_model=RemittanceResult,
    summary="Match a customer remittance to an open AR item and apply cash",
)
def apply_remittance(
    remittance: Remittance, service: RemittanceService = Depends(get_remittance_service)
) -> RemittanceResult:
    """Apply an inbound remittance against the referenced open AR item."""
    return service.apply(remittance)
