"""Tests for the matching engine and service (Task 6).

Pure logic, so it runs fully locally — including an integration test that pushes
the Task 1 labelled scenarios through the engine and checks the classification
matches the ground-truth expectation.
"""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from invoice_agent.matching import engine
from invoice_agent.matching.dedup import DedupStore
from invoice_agent.matching.service import MatchService
from invoice_agent.matching.tolerances import ToleranceProvider, Tolerances
from invoice_agent.schemas import (
    DocumentType,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    LineItem,
    MatchStatus,
    MatchType,
    PurchaseOrder,
)
from invoice_agent.synthetic.master import build_master
from invoice_agent.synthetic.scenarios import Scenario, derive_from_po

TOL = Tolerances(
    price_tolerance_pct=0.02, qty_tolerance_pct=0.0, amount_tolerance_abs=Decimal("1.00")
)


def _line(no: int, sku: str, desc: str, qty: str, price: str) -> LineItem:
    amount = (Decimal(qty) * Decimal(price)).quantize(Decimal("0.01"))
    return LineItem(
        line_no=no,
        sku=sku,
        description=desc,
        quantity=Decimal(qty),
        unit_price=Decimal(price),
        amount=amount,
    )


def _po() -> PurchaseOrder:
    lines = [_line(1, "SKU-1", "Widget", "10", "2.50"), _line(2, "SKU-2", "Gadget", "4", "10.00")]
    total = sum((line.amount for line in lines), Decimal(0))
    return PurchaseOrder(
        po_number="PO-1",
        vendor_id="V-1",
        vendor_name="Acme",
        order_date=date(2026, 8, 1),
        lines=lines,
        total_amount=total,
    )


def _gr() -> GoodsReceipt:
    return GoodsReceipt(
        gr_number="GR-1",
        po_number="PO-1",
        receipt_date=date(2026, 8, 3),
        lines=[
            GoodsReceiptLine(
                line_no=1, sku="SKU-1", description="Widget", quantity_received=Decimal("10")
            ),
            GoodsReceiptLine(
                line_no=2, sku="SKU-2", description="Gadget", quantity_received=Decimal("4")
            ),
        ],
    )


def _invoice(lines: list[LineItem]) -> Invoice:
    total = sum((line.amount for line in lines), Decimal(0))
    return Invoice(
        invoice_id="i1",
        invoice_number="90001",
        vendor_name="Acme",
        po_number="PO-1",
        invoice_date=date(2026, 8, 20),
        lines=lines,
        total_amount=total,
    )


def test_clean_three_way_match() -> None:
    result = engine.match(_invoice(_po().lines), _po(), _gr(), TOL)
    assert result.status is MatchStatus.MATCHED
    assert result.match_type is MatchType.THREE_WAY
    assert result.requires_human is False


def test_two_way_when_no_goods_receipt() -> None:
    result = engine.match(_invoice(_po().lines), _po(), None, TOL)
    assert result.status is MatchStatus.MATCHED
    assert result.match_type is MatchType.TWO_WAY


def test_price_variance_beyond_tolerance() -> None:
    lines = [_line(1, "SKU-1", "Widget", "10", "2.90"), _line(2, "SKU-2", "Gadget", "4", "10.00")]
    result = engine.match(_invoice(lines), _po(), _gr(), TOL)
    assert result.status is MatchStatus.PRICE_VARIANCE
    assert result.requires_human is True
    assert any(v.field == "unit_price" and not v.within_tolerance for v in result.variances)


def test_qty_variance() -> None:
    lines = [_line(1, "SKU-1", "Widget", "12", "2.50"), _line(2, "SKU-2", "Gadget", "4", "10.00")]
    result = engine.match(_invoice(lines), _po(), _gr(), TOL)
    assert result.status is MatchStatus.QTY_VARIANCE


def test_partial_when_line_missing() -> None:
    result = engine.match(_invoice([_line(1, "SKU-1", "Widget", "10", "2.50")]), _po(), _gr(), TOL)
    assert result.status is MatchStatus.PARTIAL
    assert any(v.actual == "(not invoiced)" for v in result.variances)


def test_missing_po() -> None:
    result = engine.match(_invoice(_po().lines), None, None, TOL)
    assert result.status is MatchStatus.MISSING_PO
    assert result.requires_human is True


# --- Service-level tests (resolution + dedup) ---
class _FakeGateway:
    def __init__(self, pos: list[PurchaseOrder], grs: dict[str, list[GoodsReceipt]]) -> None:
        self._pos = {p.po_number: p for p in pos}
        self._grs = grs

    def get_purchase_order(self, po_number: str) -> PurchaseOrder | None:
        return self._pos.get(po_number)

    def get_goods_receipts(self, po_number: str) -> list[GoodsReceipt]:
        return self._grs.get(po_number, [])


def _service() -> MatchService:
    return MatchService(
        erp=_FakeGateway([_po()], {"PO-1": [_gr()]}),
        tolerances=ToleranceProvider(TOL),
        dedup=DedupStore(),
        rag=None,
    )


def test_service_matches_by_po_number() -> None:
    result = _service().match_invoice(_invoice(_po().lines))
    assert result.status is MatchStatus.MATCHED
    assert result.po_number == "PO-1"


def test_service_missing_po_without_rag() -> None:
    inv = _invoice(_po().lines)
    inv = inv.model_copy(update={"po_number": "PO-DOES-NOT-EXIST"})
    result = _service().match_invoice(inv)
    assert result.status is MatchStatus.MISSING_PO


def test_service_detects_duplicate() -> None:
    service = _service()
    inv = _invoice(_po().lines).model_copy(update={"dedup_hash": "abc123"})
    assert service.match_invoice(inv).status is MatchStatus.MATCHED
    assert service.match_invoice(inv).status is MatchStatus.DUPLICATE


# --- Integration: Task 1 labelled scenarios through the engine ---
def test_labelled_scenarios_classify_correctly() -> None:
    master = build_master(seed=42, num_pos=20)
    multi_line_po = next(po for po in master.purchase_orders if len(po.lines) >= 2)
    single_po = master.purchase_orders[0]

    cases = [
        (single_po, Scenario.CLEAN),
        (single_po, Scenario.PRICE_VARIANCE),
        (single_po, Scenario.QTY_VARIANCE),
        (multi_line_po, Scenario.PARTIAL),
    ]
    for po, scenario in cases:
        vendor = master.vendor_by_id[po.vendor_id]
        gr = master.gr_by_po.get(po.po_number)
        invoice, _printed, gt = derive_from_po(
            seq=1,
            invoice_number="90001",
            po=po,
            vendor=vendor,
            scenario=scenario,
            document_type=DocumentType.PDF,
            gr_present=gr is not None,
            fuzz_vendor=False,
            rng=random.Random(0),
        )
        result = engine.match(invoice, po, gr, TOL)
        assert result.status is gt.expected_status, (
            f"{scenario}: {result.status} != {gt.expected_status}"
        )
