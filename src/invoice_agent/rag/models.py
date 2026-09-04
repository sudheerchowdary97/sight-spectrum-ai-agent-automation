"""RAG models: a retrieved candidate Purchase Order."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class RetrievedPO(BaseModel):
    """A candidate Purchase Order returned by semantic retrieval."""

    po_number: str
    vendor_name: str = ""
    total_amount: Decimal | None = None
    score: float = 0.0
