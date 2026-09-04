"""Purchase Order — the ERP record an invoice is matched against."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.schemas.common import DomainModel, LineItem


class PurchaseOrder(DomainModel):
    """A Purchase Order as stored in (mock) ERP."""

    po_number: str
    vendor_id: str
    vendor_name: str
    currency: str = "USD"
    order_date: date
    lines: list[LineItem]
    total_amount: Decimal
    status: str = "open"  # open | closed | cancelled
