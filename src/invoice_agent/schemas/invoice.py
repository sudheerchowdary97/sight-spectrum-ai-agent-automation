"""Invoice — the document extracted from an inbound email (Task 4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import Field

from invoice_agent.schemas.common import (
    DocumentType,
    DomainModel,
    InvoiceStatus,
    LineItem,
)


class Invoice(DomainModel):
    """A vendor invoice, populated by document extraction.

    ``invoice_id`` is our internal identifier; ``invoice_number`` is the
    vendor-assigned number used for duplicate detection and PO matching.
    """

    invoice_id: str
    invoice_number: str
    vendor_name: str
    vendor_id: str | None = None
    po_number: str | None = None

    invoice_date: date
    due_date: date | None = None
    currency: str = "USD"

    lines: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total_amount: Decimal

    # Provenance — links every invoice back to its source (audit requirement).
    source_email_id: str | None = None
    source_document: str | None = None
    document_type: DocumentType | None = None

    # Workflow bookkeeping.
    status: InvoiceStatus = InvoiceStatus.RECEIVED
    dedup_hash: str | None = None
    extraction_confidence: float | None = None
