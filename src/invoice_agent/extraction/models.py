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

    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal | None = None
    sku: str | None = None


class ExtractedInvoice(BaseModel):
    """Structured fields the LLM extracts from the parsed document text."""

    invoice_number: str
    vendor_name: str
    po_number: str | None = None
    invoice_date: date
    due_date: date | None = None
    currency: str = "USD"
    lines: list[ExtractedLine] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total_amount: Decimal


class ExtractionResult(BaseModel):
    """The outcome of extraction: a validated invoice plus quality signals."""

    invoice: Invoice
    confidence: float
    warnings: list[str] = Field(default_factory=list)
