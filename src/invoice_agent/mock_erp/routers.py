"""Mock ERP HTTP routers (Task 2).

Endpoints (all under ``/api/v1``):
    GET  /health
    GET  /purchase-orders/{po_number}
    GET  /goods-receipts?po_number=...
    GET  /ar-items[?status=open]
    GET  /ar-items/{ar_item_id}
    POST /payment-journals
    GET  /payment-journals
    GET  /payment-journals/{journal_id}
    POST /cash-applications
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from invoice_agent import __version__
from invoice_agent.mock_erp.models import (
    CashApplication,
    CashApplicationRequest,
    PaymentJournalRequest,
)
from invoice_agent.mock_erp.store import DuplicateJournalError, ERPStore, NotFoundError
from invoice_agent.schemas import ARItem, GoodsReceipt, PaymentJournalEntry, PurchaseOrder

router = APIRouter(prefix="/api/v1", tags=["erp"])


def get_store(request: Request) -> ERPStore:
    """Dependency: the ERP store held on application state."""
    return request.app.state.store


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="mock-erp", version=__version__)


@router.get(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrder,
    summary="Fetch a Purchase Order",
)
async def get_purchase_order(po_number: str, store: ERPStore = Depends(get_store)) -> PurchaseOrder:
    try:
        return store.get_purchase_order(po_number)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/goods-receipts",
    response_model=list[GoodsReceipt],
    summary="List Goods Receipts for a PO",
)
async def get_goods_receipts(
    po_number: str = Query(..., description="PO number to fetch receipts for"),
    store: ERPStore = Depends(get_store),
) -> list[GoodsReceipt]:
    return store.get_goods_receipts(po_number)


@router.get("/ar-items", response_model=list[ARItem], summary="List AR items")
async def list_ar_items(
    status: str | None = Query(None, description="Filter by status, e.g. 'open'"),
    store: ERPStore = Depends(get_store),
) -> list[ARItem]:
    return store.list_ar_items(status=status)


@router.get("/ar-items/{ar_item_id}", response_model=ARItem, summary="Fetch an AR item")
async def get_ar_item(ar_item_id: str, store: ERPStore = Depends(get_store)) -> ARItem:
    try:
        return store.get_ar_item(ar_item_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/payment-journals",
    response_model=PaymentJournalEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Post a Payment Journal entry",
)
async def post_payment_journal(
    req: PaymentJournalRequest, store: ERPStore = Depends(get_store)
) -> PaymentJournalEntry:
    try:
        return store.post_journal(req)
    except DuplicateJournalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "invoice_number": exc.invoice_number,
                "existing_journal_id": exc.existing_journal_id,
            },
        ) from exc


@router.get(
    "/payment-journals",
    response_model=list[PaymentJournalEntry],
    summary="List posted Payment Journals",
)
async def list_payment_journals(
    store: ERPStore = Depends(get_store),
) -> list[PaymentJournalEntry]:
    return store.list_journals()


@router.get(
    "/payment-journals/{journal_id}",
    response_model=PaymentJournalEntry,
    summary="Fetch a Payment Journal entry",
)
async def get_payment_journal(
    journal_id: str, store: ERPStore = Depends(get_store)
) -> PaymentJournalEntry:
    try:
        return store.get_journal(journal_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/cash-applications",
    response_model=CashApplication,
    status_code=status.HTTP_201_CREATED,
    summary="Apply a remittance to an AR item",
)
async def post_cash_application(
    req: CashApplicationRequest, store: ERPStore = Depends(get_store)
) -> CashApplication:
    try:
        return store.apply_cash(req)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
