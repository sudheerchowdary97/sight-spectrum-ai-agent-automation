"""PO matching endpoint (POST /api/v1/match-po)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from invoice_agent.matching.service import MatchService
from invoice_agent.schemas import Invoice, MatchResult

router = APIRouter(tags=["matching"])


def get_match_service(request: Request) -> MatchService:
    """Dependency: the match service held on application state."""
    return request.app.state.match_service


@router.post(
    "/match-po",
    response_model=MatchResult,
    summary="Match an extracted invoice against its PO (2-way / 3-way)",
)
def match_po(invoice: Invoice, service: MatchService = Depends(get_match_service)) -> MatchResult:
    """Resolve the PO (by number or RAG), pull the Goods Receipt, and match.

    Returns a MatchResult classifying the outcome (matched / price_variance /
    qty_variance / partial / missing_po / duplicate) with per-line variances.
    """
    return service.match_invoice(invoice)
