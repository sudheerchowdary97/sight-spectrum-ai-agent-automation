"""Payment-journal posting endpoint (POST /api/v1/post-payment-journal)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from invoice_agent.posting import DuplicateJournalError, PostingService
from invoice_agent.schemas import Invoice, PaymentJournalEntry

router = APIRouter(tags=["payment"])


def get_posting_service(request: Request) -> PostingService:
    return request.app.state.posting_service


@router.post(
    "/post-payment-journal",
    response_model=PaymentJournalEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Post a Payment Journal entry for an approved invoice",
)
def post_payment_journal(
    invoice: Invoice, service: PostingService = Depends(get_posting_service)
) -> PaymentJournalEntry:
    """Post the AP Payment Journal for an approved invoice via the ERP.

    Returns the posted entry; a duplicate (already-posted invoice) yields 409.
    """
    try:
        return service.post(invoice)
    except DuplicateJournalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "invoice_number": exc.invoice_number, "erp": exc.detail},
        ) from exc
