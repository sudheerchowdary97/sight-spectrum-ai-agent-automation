"""Tests for document extraction (Task 4).

The Docling + Ollama path is exercised in Docker (see README runbook); here the
parser and LLM are faked so the normalisation, dedup-hashing, reconciliation
confidence, and orchestration logic are tested deterministically.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.extraction.models import ExtractedInvoice, ExtractedLine
from invoice_agent.extraction.normalizer import compute_dedup_hash, to_extraction_result
from invoice_agent.extraction.service import ExtractionService
from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.schemas import DocumentType, InvoiceStatus


def _ingested() -> IngestedDocument:
    return IngestedDocument(
        document_id="email-INV-00002:INV-00002.pdf",
        email_id="email-INV-00002",
        sender="Acme Corp <ap@acme.example>",
        subject="Invoice 90002",
        attachment_filename="INV-00002.pdf",
        content_type="application/pdf",
        document_type=DocumentType.PDF,
        storage_path="/tmp/whatever.pdf",
        size_bytes=1234,
        content_sha256="deadbeef",
    )


def _extracted(**overrides: object) -> ExtractedInvoice:
    data = {
        "invoice_number": "90002",
        "vendor_name": "Acme Corp",
        "po_number": "PO-10002",
        "invoice_date": date(2026, 8, 20),
        "currency": "USD",
        "lines": [
            ExtractedLine(
                description="Widget",
                quantity=Decimal("10"),
                unit_price=Decimal("2.50"),
                amount=Decimal("25.00"),
                sku="SKU-1",
            )
        ],
        "total_amount": Decimal("25.00"),
    }
    data.update(overrides)
    return ExtractedInvoice(**data)  # type: ignore[arg-type]


class _FakeParser:
    def __init__(self, text: str = "parsed text") -> None:
        self.text = text
        self.calls: list[str] = []

    def to_text(self, storage_path: str, document_type: DocumentType) -> str:
        self.calls.append(storage_path)
        return self.text


class _FakeLLM:
    def __init__(self, extracted: ExtractedInvoice) -> None:
        self.extracted = extracted

    def extract_invoice(self, text: str) -> ExtractedInvoice:
        return self.extracted


def test_service_produces_validated_invoice() -> None:
    parser = _FakeParser()
    service = ExtractionService(parser, _FakeLLM(_extracted()))
    result = service.extract(_ingested())

    inv = result.invoice
    assert parser.calls == ["/tmp/whatever.pdf"]
    assert inv.invoice_number == "90002"
    assert inv.status is InvoiceStatus.EXTRACTED
    assert inv.source_email_id == "email-INV-00002"
    assert inv.document_type is DocumentType.PDF
    assert inv.dedup_hash
    assert result.confidence == 1.0
    assert result.warnings == []


def test_amount_computed_when_missing() -> None:
    extracted = _extracted(
        lines=[ExtractedLine(description="X", quantity=Decimal("3"), unit_price=Decimal("4.00"))],
        total_amount=Decimal("12.00"),
    )
    result = to_extraction_result(extracted, _ingested())
    assert result.invoice.lines[0].amount == Decimal("12.00")
    assert result.confidence == 1.0


def test_total_mismatch_lowers_confidence() -> None:
    extracted = _extracted(total_amount=Decimal("999.00"))  # lines sum to 25.00
    result = to_extraction_result(extracted, _ingested())
    assert result.confidence <= 0.6
    assert any("stated total" in w for w in result.warnings)


def test_missing_po_warns_but_keeps_confidence() -> None:
    result = to_extraction_result(_extracted(po_number=None), _ingested())
    assert any("PO number" in w for w in result.warnings)
    assert result.confidence == 1.0


def test_dedup_hash_stability_and_sensitivity() -> None:
    base = compute_dedup_hash("90002", "Acme Corp", Decimal("25.00"))
    assert base == compute_dedup_hash("90002", "  acme corp ", Decimal("25.000"))
    assert base != compute_dedup_hash("90002", "Acme Corporation", Decimal("25.00"))
    assert base != compute_dedup_hash("90003", "Acme Corp", Decimal("25.00"))
