"""RAG service: index master POs and retrieve candidates for an invoice."""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger
from invoice_agent.rag.base import POIndex
from invoice_agent.rag.documents import invoice_to_query
from invoice_agent.rag.models import RetrievedPO
from invoice_agent.schemas import Invoice, PurchaseOrder

log = get_logger("rag")


class RagService:
    """Index Purchase Orders and retrieve candidates for invoices."""

    def __init__(self, index: POIndex) -> None:
        self._index = index

    def index_master(self, purchase_orders: list[PurchaseOrder]) -> None:
        self._index.index_purchase_orders(purchase_orders)

    def find_candidate_pos(self, invoice: Invoice, top_k: int = 5) -> list[RetrievedPO]:
        """Return the most similar candidate POs for ``invoice``."""
        candidates = self._index.retrieve(invoice_to_query(invoice), top_k=top_k)
        log.info(
            "rag.retrieve",
            invoice_number=invoice.invoice_number,
            candidates=[c.po_number for c in candidates],
        )
        return candidates


def build_rag_service(settings: Settings) -> RagService:
    """Build the real LlamaIndex + PGVector RAG service."""
    from invoice_agent.rag.index import LlamaIndexPOIndex

    return RagService(LlamaIndexPOIndex(settings))
