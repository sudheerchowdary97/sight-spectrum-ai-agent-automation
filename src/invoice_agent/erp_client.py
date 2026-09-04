"""HTTP client for the ERP service (mock or real).

Implements the :class:`~invoice_agent.matching.gateway.PoGateway` reads plus the
write operations used by payment posting (Task 9) and the AR mirror (Task 10).
"""

from __future__ import annotations

from typing import Any

import httpx

from invoice_agent.schemas import ARItem, GoodsReceipt, PaymentJournalEntry, PurchaseOrder


class ErpClient:
    """Thin synchronous client over the ERP REST API."""

    def __init__(self, base_url: str, *, timeout: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def _url(self, path: str) -> str:
        return f"{self._base}/api/v1/{path.lstrip('/')}"

    # ---------------------------------------------------------------- reads
    def get_purchase_order(self, po_number: str) -> PurchaseOrder | None:
        resp = self._client.get(self._url(f"purchase-orders/{po_number}"))
        if resp.status_code == httpx.codes.NOT_FOUND:
            return None
        resp.raise_for_status()
        return PurchaseOrder.model_validate(resp.json())

    def get_goods_receipts(self, po_number: str) -> list[GoodsReceipt]:
        resp = self._client.get(self._url("goods-receipts"), params={"po_number": po_number})
        resp.raise_for_status()
        return [GoodsReceipt.model_validate(x) for x in resp.json()]

    def list_ar_items(self, status: str | None = None) -> list[ARItem]:
        params = {"status": status} if status else None
        resp = self._client.get(self._url("ar-items"), params=params)
        resp.raise_for_status()
        return [ARItem.model_validate(x) for x in resp.json()]

    # ---------------------------------------------------------------- writes
    def post_payment_journal(self, payload: dict[str, Any]) -> PaymentJournalEntry:
        resp = self._client.post(self._url("payment-journals"), json=payload)
        resp.raise_for_status()
        return PaymentJournalEntry.model_validate(resp.json())

    def apply_cash(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(self._url("cash-applications"), json=payload)
        resp.raise_for_status()
        return resp.json()
