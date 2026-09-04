"""Normalise LLM-extracted fields into a validated domain Invoice.

Also computes the duplicate-detection hash and a confidence score based on
whether the line items reconcile to the stated total.
"""

from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal

from invoice_agent.extraction.models import ExtractedInvoice, ExtractionResult
from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.schemas import Invoice, InvoiceStatus, LineItem

CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_dedup_hash(invoice_number: str, vendor_name: str, total_amount: Decimal) -> str:
    """Stable hash for duplicate detection (invoice # + vendor + amount).

    Vendor name is case/space-normalised and the total quantised, so a re-sent
    identical invoice hashes the same while genuinely different invoices do not.
    """
    key = f"{invoice_number.strip().lower()}|{vendor_name.strip().lower()}|{_money(total_amount)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def to_extraction_result(
    extracted: ExtractedInvoice, ingested: IngestedDocument, *, base_confidence: float = 1.0
) -> ExtractionResult:
    """Convert lenient LLM output into a strict, validated :class:`ExtractionResult`."""
    warnings: list[str] = []

    lines: list[LineItem] = []
    for idx, line in enumerate(extracted.lines, start=1):
        amount = line.amount if line.amount is not None else _money(line.quantity * line.unit_price)
        lines.append(
            LineItem(
                line_no=idx,
                sku=line.sku,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=amount,
                currency=extracted.currency,
            )
        )

    confidence = base_confidence
    computed_total = _money(sum((line.amount for line in lines), Decimal(0)))
    if lines and abs(computed_total - _money(extracted.total_amount)) > CENT:
        warnings.append(
            f"line items sum to {computed_total} but stated total is "
            f"{_money(extracted.total_amount)}"
        )
        confidence = min(confidence, 0.6)
    if not lines:
        warnings.append("no line items extracted")
        confidence = min(confidence, 0.5)
    if not extracted.po_number:
        warnings.append("no PO number on invoice")

    invoice = Invoice(
        invoice_id=ingested.document_id,
        invoice_number=extracted.invoice_number,
        vendor_name=extracted.vendor_name,
        po_number=extracted.po_number,
        invoice_date=extracted.invoice_date,
        due_date=extracted.due_date,
        currency=extracted.currency,
        lines=lines,
        subtotal=extracted.subtotal,
        tax=extracted.tax,
        total_amount=extracted.total_amount,
        source_email_id=ingested.email_id,
        source_document=ingested.attachment_filename,
        document_type=ingested.document_type,
        status=InvoiceStatus.EXTRACTED,
        dedup_hash=compute_dedup_hash(
            extracted.invoice_number, extracted.vendor_name, extracted.total_amount
        ),
        extraction_confidence=round(confidence, 3),
    )
    return ExtractionResult(invoice=invoice, confidence=round(confidence, 3), warnings=warnings)
