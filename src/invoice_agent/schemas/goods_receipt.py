"""Goods Receipt — evidence of delivery, used for the 3-way match."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.schemas.common import DomainModel


class GoodsReceiptLine(DomainModel):
    """A received quantity for a single PO line."""

    line_no: int
    sku: str | None = None
    description: str
    quantity_received: Decimal


class GoodsReceipt(DomainModel):
    """A Goods Receipt linked to a Purchase Order."""

    gr_number: str
    po_number: str
    receipt_date: date
    lines: list[GoodsReceiptLine]
