"""Extraction models: the lenient LLM-output schema and the extraction result.

``ExtractedInvoice`` is the schema we ask the LLM to fill (and validate its JSON
against). It is intentionally close to the domain :class:`Invoice` but tolerant
of what a model might emit; :mod:`.normalizer` converts it into the strict
domain object.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from invoice_agent.schemas import Invoice


class ExtractedLine(BaseModel):
    """A single line item as produced by the LLM."""

    description: str = Field(description="Item description text from the Description column")
    quantity: Decimal = Field(description="Quantity from the Qty column")
    unit_price: Decimal = Field(description="Unit price from the Unit column")
    amount: Decimal | None = Field(default=None, description="Line total from the Amount column")
    sku: str | None = Field(
        default=None, description="Item code from the SKU column, e.g. 'SKU-1001'; null if none"
    )


class ExtractedInvoice(BaseModel):
    """Structured fields the LLM extracts from the parsed document text."""

    invoice_number: str = Field(description="Invoice number, labelled 'Invoice #:', e.g. '90005'")
    vendor_name: str = Field(description="Vendor/supplier name, labelled 'Vendor:'")
    po_number: str | None = Field(
        default=None,
        description=(
            "Purchase order number, labelled 'PO #:', e.g. 'PO-10005'. "
            "Use null ONLY if it is missing or shown as 'N/A'."
        ),
    )
    invoice_date: date = Field(description="Invoice date, labelled 'Date:' (YYYY-MM-DD)")
    due_date: date | None = Field(default=None, description="Due date, labelled 'Due:' (YYYY-MM-DD)")
    currency: str = Field(default="USD", description="ISO currency code, e.g. 'USD'")
    lines: list[ExtractedLine] = Field(
        default_factory=list, description="Every row of the line-item table"
    )
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total_amount: Decimal = Field(description="Grand total, labelled 'Total:'")


class ExtractionResult(BaseModel):
    """The outcome of extraction: a validated invoice plus quality signals."""

    invoice: Invoice
    confidence: float
    warnings: list[str] = Field(default_factory=list)
