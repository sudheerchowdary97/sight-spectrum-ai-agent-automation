"""Payment Journal — the entry posted to the ERP for approved invoices (Task 9)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from invoice_agent.schemas.common import DomainModel, utcnow


class PaymentJournalEntry(DomainModel):
    """An accounts-payable journal entry posted to the ERP."""

    journal_id: str
    invoice_number: str
    po_number: str | None = None
    vendor_id: str | None = None
    vendor_name: str

    amount: Decimal
    currency: str = "USD"
    gl_account: str = "2000-AP"  # accounts payable
    posting_date: date

    status: str = "posted"  # posted | pending | failed
    erp_reference: str | None = None  # id returned by the ERP on success
    created_at: datetime = Field(default_factory=utcnow)
