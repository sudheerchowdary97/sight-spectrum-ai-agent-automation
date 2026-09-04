"""Scenario derivation: turn a PO into an invoice with a known expected outcome.

Each generated invoice is tagged with a :class:`GroundTruthRecord` so the
evaluation harness (Task 13) can score extraction accuracy, match rate, and
straight-through-processing (STP) rate without any manual labelling.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from invoice_agent.schemas import (
    DocumentType,
    Invoice,
    InvoiceStatus,
    LineItem,
    MatchStatus,
    MatchType,
    PurchaseOrder,
)
from invoice_agent.synthetic.master import CATALOG, REFERENCE_DATE, Vendor, money


class Scenario(StrEnum):
    """The controlled test scenarios we generate."""

    CLEAN = "clean"
    PRICE_VARIANCE = "price_variance"
    QTY_VARIANCE = "qty_variance"
    PARTIAL = "partial"
    MISSING_PO = "missing_po"
    DUPLICATE = "duplicate"


# Scenario -> expected match status the pipeline should reach.
SCENARIO_STATUS: dict[Scenario, MatchStatus] = {
    Scenario.CLEAN: MatchStatus.MATCHED,
    Scenario.PRICE_VARIANCE: MatchStatus.PRICE_VARIANCE,
    Scenario.QTY_VARIANCE: MatchStatus.QTY_VARIANCE,
    Scenario.PARTIAL: MatchStatus.PARTIAL,
    Scenario.MISSING_PO: MatchStatus.MISSING_PO,
    Scenario.DUPLICATE: MatchStatus.DUPLICATE,
}

# Scenarios that must be escalated to a human rather than auto-posted.
HUMAN_REVIEW = {
    Scenario.PRICE_VARIANCE,
    Scenario.QTY_VARIANCE,
    Scenario.PARTIAL,
    Scenario.MISSING_PO,
    Scenario.DUPLICATE,
}


class GroundTruthRecord(BaseModel):
    """The labelled expectation for a single generated invoice."""

    invoice_number: str
    scenario: Scenario
    expected_status: MatchStatus
    expected_match_type: MatchType
    expected_requires_human: bool

    po_number: str | None = None
    linked_po_exists: bool = False
    duplicate_of: str | None = None

    document_type: DocumentType
    email_id: str
    source_files: list[str] = Field(default_factory=list)

    # Printed values on the document — the target for extraction-accuracy scoring.
    expected_fields: dict[str, str | int] = Field(default_factory=dict)


def _expected_fields(invoice: Invoice, printed_vendor_name: str) -> dict[str, str | int]:
    return {
        "invoice_number": invoice.invoice_number,
        "vendor_name": printed_vendor_name,
        "invoice_date": invoice.invoice_date.isoformat(),
        "currency": invoice.currency,
        "total_amount": f"{invoice.total_amount:.2f}",
        "po_number": invoice.po_number or "",
        "line_count": len(invoice.lines),
    }


def fuzz_vendor_name(name: str, rng: random.Random) -> str:
    """Return a plausibly-different rendering of a vendor name (tests fuzzy RAG)."""
    variants = [
        name.upper(),
        name.replace(",", ""),
        f"{name} Inc." if not name.endswith(("Inc", "Inc.", "LLC", "Ltd")) else name,
        name.replace(" and ", " & "),
        name.split(" ")[0] + " Corp.",
    ]
    return rng.choice(variants)


def _invoice_dates(rng: random.Random):
    invoice_date = REFERENCE_DATE - timedelta(days=rng.randint(0, 18))
    return invoice_date, invoice_date + timedelta(days=30)


def derive_from_po(
    *,
    seq: int,
    invoice_number: str,
    po: PurchaseOrder,
    vendor: Vendor,
    scenario: Scenario,
    document_type: DocumentType,
    gr_present: bool,
    fuzz_vendor: bool,
    rng: random.Random,
) -> tuple[Invoice, str, GroundTruthRecord]:
    """Derive an invoice (and its ground truth) from a PO for a given scenario.

    Returns ``(invoice, printed_vendor_name, ground_truth)``. The printed vendor
    name may differ from the canonical name when ``fuzz_vendor`` is set.
    """
    lines: list[LineItem] = [line.model_copy(deep=True) for line in po.lines]

    if scenario is Scenario.PRICE_VARIANCE:
        target = rng.randrange(len(lines))
        factor = Decimal(str(round(rng.uniform(1.06, 1.18), 4)))  # beyond typical tolerance
        new_price = money(lines[target].unit_price * factor)
        lines[target] = lines[target].model_copy(
            update={"unit_price": new_price, "amount": money(new_price * lines[target].quantity)}
        )
    elif scenario is Scenario.QTY_VARIANCE:
        target = rng.randrange(len(lines))
        delta = Decimal(rng.choice([-2, -1, 1, 2, 3]))
        new_qty = max(Decimal(1), lines[target].quantity + delta)
        lines[target] = lines[target].model_copy(
            update={"quantity": new_qty, "amount": money(new_qty * lines[target].unit_price)}
        )
    elif scenario is Scenario.PARTIAL and len(lines) > 1:
        keep = rng.randint(1, len(lines) - 1)
        lines = lines[:keep]

    printed_vendor_name = fuzz_vendor_name(po.vendor_name, rng) if fuzz_vendor else po.vendor_name
    invoice_date, due_date = _invoice_dates(rng)
    total = money(sum((line.amount for line in lines), Decimal(0)))

    invoice = Invoice(
        invoice_id=f"INV-{seq:05d}",
        invoice_number=invoice_number,
        vendor_name=printed_vendor_name,
        vendor_id=po.vendor_id,
        po_number=po.po_number,
        invoice_date=invoice_date,
        due_date=due_date,
        currency="USD",
        lines=lines,
        subtotal=total,
        total_amount=total,
        status=InvoiceStatus.RECEIVED,
    )

    match_type = MatchType.THREE_WAY if gr_present else MatchType.TWO_WAY
    gt = GroundTruthRecord(
        invoice_number=invoice_number,
        scenario=scenario,
        expected_status=SCENARIO_STATUS[scenario],
        expected_match_type=match_type,
        expected_requires_human=scenario in HUMAN_REVIEW,
        po_number=po.po_number,
        linked_po_exists=True,
        document_type=document_type,
        email_id="",  # filled in when the email fixture is written
        expected_fields=_expected_fields(invoice, printed_vendor_name),
    )
    return invoice, printed_vendor_name, gt


def build_missing_po(
    *,
    seq: int,
    invoice_number: str,
    vendor: Vendor,
    document_type: DocumentType,
    rng: random.Random,
) -> tuple[Invoice, str, GroundTruthRecord]:
    """Build an invoice that references a PO which does not exist in the ERP."""
    n_lines = rng.randint(1, 3)
    picks = rng.sample(CATALOG, n_lines)
    lines: list[LineItem] = []
    for idx, (sku, desc, base_price) in enumerate(picks, start=1):
        qty = Decimal(rng.randint(1, 20))
        unit_price = money(Decimal(base_price))
        lines.append(
            LineItem(
                line_no=idx,
                sku=sku,
                description=desc,
                quantity=qty,
                unit_price=unit_price,
                amount=money(qty * unit_price),
            )
        )

    bogus_po = f"PO-{rng.randint(90000, 99999)}"  # not in master
    invoice_date = REFERENCE_DATE - timedelta(days=rng.randint(0, 18))
    total = money(sum((line.amount for line in lines), Decimal(0)))

    invoice = Invoice(
        invoice_id=f"INV-{seq:05d}",
        invoice_number=invoice_number,
        vendor_name=vendor.name,
        vendor_id=vendor.vendor_id,
        po_number=bogus_po,
        invoice_date=invoice_date,
        due_date=invoice_date + timedelta(days=30),
        currency="USD",
        lines=lines,
        subtotal=total,
        total_amount=total,
        status=InvoiceStatus.RECEIVED,
    )
    gt = GroundTruthRecord(
        invoice_number=invoice_number,
        scenario=Scenario.MISSING_PO,
        expected_status=MatchStatus.MISSING_PO,
        expected_match_type=MatchType.TWO_WAY,
        expected_requires_human=True,
        po_number=bogus_po,
        linked_po_exists=False,
        document_type=document_type,
        email_id="",
        expected_fields=_expected_fields(invoice, vendor.name),
    )
    return invoice, vendor.name, gt
