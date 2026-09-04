"""Accounts-Receivable mirror track — remittances applied to open AR items (Task 10)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import Field

from invoice_agent.schemas.common import DomainModel


class ARItem(DomainModel):
    """An open accounts-receivable item awaiting customer payment."""

    ar_item_id: str
    customer_id: str
    customer_name: str
    invoice_number: str
    open_amount: Decimal
    currency: str = "USD"
    due_date: date | None = None
    status: str = "open"  # open | applied | partially_applied


class Remittance(DomainModel):
    """An inbound customer remittance to be matched against open AR items."""

    remittance_id: str
    customer_name: str
    amount: Decimal
    currency: str = "USD"
    references: list[str] = Field(default_factory=list)  # invoice numbers referenced
    remittance_date: date
    source_email_id: str | None = None
