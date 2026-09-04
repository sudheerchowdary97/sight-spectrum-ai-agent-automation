"""Shared primitives and enumerations for the domain model.

Every business object in the pipeline is built from these types so that
extraction, matching, posting, and audit all speak the same language.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base class for all domain models: strict, immutable-ish, whitespace-safe."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class DocumentType(StrEnum):
    """Source format of an ingested invoice document."""

    PDF = "pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"
    HTML = "html"


class MatchType(StrEnum):
    """Whether a Goods Receipt participated in the match."""

    TWO_WAY = "two_way"  # Invoice ↔ PO
    THREE_WAY = "three_way"  # Invoice ↔ PO ↔ Goods Receipt


class MatchStatus(StrEnum):
    """Outcome of the matching engine (Task 6)."""

    MATCHED = "matched"
    PRICE_VARIANCE = "price_variance"
    QTY_VARIANCE = "qty_variance"
    MISSING_PO = "missing_po"
    DUPLICATE = "duplicate"
    PARTIAL = "partial"


class InvoiceStatus(StrEnum):
    """Lifecycle state of an invoice as it moves through the workflow."""

    RECEIVED = "received"
    EXTRACTED = "extracted"
    MATCHED = "matched"
    EXCEPTION = "exception"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"


class LineItem(DomainModel):
    """A single billed line, common to invoices and purchase orders."""

    line_no: int
    sku: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    currency: str = "USD"


def utcnow() -> datetime:
    """Timezone-aware current UTC timestamp."""
    return datetime.now(UTC)
