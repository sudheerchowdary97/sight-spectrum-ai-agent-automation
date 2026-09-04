"""Index interface (protocol) for candidate-PO retrieval."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_agent.rag.models import RetrievedPO
from invoice_agent.schemas import PurchaseOrder


@runtime_checkable
class POIndex(Protocol):
    """A searchable index of Purchase Orders."""

    def index_purchase_orders(self, purchase_orders: list[PurchaseOrder]) -> None:
        """Add/replace the given POs in the index."""
        ...

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedPO]:
        """Return the ``top_k`` POs most similar to ``query``, best first."""
        ...
