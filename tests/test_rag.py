"""Tests for the RAG retrieval layer (Task 5).

The real LlamaIndex + PGVector + Ollama path runs in Docker (see README runbook).
Here the dependency-free InMemoryPOIndex exercises the document/query builders and
the retrieval/service logic deterministically.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.rag.documents import invoice_to_query, po_to_text
from invoice_agent.rag.index import InMemoryPOIndex
from invoice_agent.rag.service import RagService
from invoice_agent.schemas import Invoice, LineItem, PurchaseOrder


def _po(po_number: str, vendor: str, sku: str, desc: str, qty: str, price: str) -> PurchaseOrder:
    amount = Decimal(qty) * Decimal(price)
    return PurchaseOrder(
        po_number=po_number,
        vendor_id=f"V-{po_number[-1]}",
        vendor_name=vendor,
        order_date=date(2026, 8, 1),
        lines=[
            LineItem(
                line_no=1,
                sku=sku,
                description=desc,
                quantity=Decimal(qty),
                unit_price=Decimal(price),
                amount=amount,
            )
        ],
        total_amount=amount,
    )


def _pos() -> list[PurchaseOrder]:
    return [
        _po("PO-1", "Acme Corporation", "SKU-1", "A4 Copy Paper", "10", "4.25"),
        _po("PO-2", "Globex Ltd", "SKU-2", "Mechanical Keyboard", "3", "64.90"),
        _po("PO-3", "Initech LLC", "SKU-3", "Ergonomic Office Chair", "2", "245.00"),
    ]


def _invoice(vendor: str, sku: str, desc: str, qty: str, price: str) -> Invoice:
    amount = Decimal(qty) * Decimal(price)
    return Invoice(
        invoice_id="i1",
        invoice_number="90001",
        vendor_name=vendor,
        invoice_date=date(2026, 8, 20),
        total_amount=amount,
        lines=[
            LineItem(
                line_no=1,
                sku=sku,
                description=desc,
                quantity=Decimal(qty),
                unit_price=Decimal(price),
                amount=amount,
            )
        ],
    )


def test_document_and_query_share_shape() -> None:
    po = _pos()[0]
    assert "Vendor: Acme Corporation" in po_to_text(po)
    assert "A4 Copy Paper" in po_to_text(po)
    q = invoice_to_query(_invoice("Acme", "SKU-1", "A4 Copy Paper", "10", "4.25"))
    assert q.startswith("Vendor:")
    assert "A4 Copy Paper" in q


def test_retrieval_ranks_matching_po_first() -> None:
    index = InMemoryPOIndex()
    index.index_purchase_orders(_pos())
    service = RagService(index)

    # Invoice for the keyboard PO — should retrieve PO-2 first.
    candidates = service.find_candidate_pos(
        _invoice("Globex Ltd", "SKU-2", "Mechanical Keyboard", "3", "64.90"), top_k=3
    )
    assert candidates[0].po_number == "PO-2"
    assert candidates[0].score > 0


def test_retrieval_robust_to_fuzzy_vendor_name() -> None:
    index = InMemoryPOIndex()
    index.index_purchase_orders(_pos())
    service = RagService(index)

    # Fuzzed vendor name ("ACME CORP." vs "Acme Corporation") but same line item.
    candidates = service.find_candidate_pos(
        _invoice("ACME CORP.", "SKU-1", "A4 Copy Paper", "10", "4.25"), top_k=3
    )
    assert candidates[0].po_number == "PO-1"
