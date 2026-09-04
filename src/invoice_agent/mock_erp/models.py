"""API request/response models for the Mock ERP (Task 2).

These are the wire contracts for the ERP endpoints. Core domain objects
(``PurchaseOrder``, ``GoodsReceipt``, ``ARItem``, ``PaymentJournalEntry``) are
reused from :mod:`invoice_agent.schemas`; this module adds the request bodies
and the cash-application response.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentJournalRequest(BaseModel):
    """Request to post an accounts-payable Payment Journal entry."""

    invoice_number: str
    vendor_name: str
    vendor_id: str | None = None
    po_number: str | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    gl_account: str = "2000-AP"
    posting_date: date | None = None  # defaults to today at the ERP if omitted


class CashApplicationRequest(BaseModel):
    """Request to apply an inbound remittance against an open AR item."""

    remittance_id: str
    ar_item_id: str
    amount: Decimal = Field(gt=0)
    currency: str = "USD"


class CashApplication(BaseModel):
    """Result of applying cash to an AR item."""

    application_id: str
    remittance_id: str
    ar_item_id: str
    amount_applied: Decimal
    remaining_open: Decimal
    status: str  # applied | partially_applied | overpaid
