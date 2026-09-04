"""Contract tests for the shared domain schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invoice_agent.schemas import (
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceStatus,
    LineItem,
    PurchaseOrder,
)


def _line(**overrides: object) -> LineItem:
    data = {
        "line_no": 1,
        "sku": "SKU-1",
        "description": "Widget",
        "quantity": Decimal("10"),
        "unit_price": Decimal("2.50"),
        "amount": Decimal("25.00"),
    }
    data.update(overrides)
    return LineItem(**data)  # type: ignore[arg-type]


def test_purchase_order_roundtrip() -> None:
    po = PurchaseOrder(
        po_number="PO-1001",
        vendor_id="V-1",
        vendor_name="Acme Corp",
        order_date=date(2026, 1, 1),
        lines=[_line()],
        total_amount=Decimal("25.00"),
    )
    assert po.po_number == "PO-1001"
    assert PurchaseOrder.model_validate_json(po.model_dump_json()) == po


def test_invoice_defaults_and_status() -> None:
    inv = Invoice(
        invoice_id="INV-internal-1",
        invoice_number="90001",
        vendor_name="Acme Corp",
        invoice_date=date(2026, 1, 5),
        lines=[_line()],
        total_amount=Decimal("25.00"),
    )
    assert inv.status is InvoiceStatus.RECEIVED
    assert inv.currency == "USD"


def test_goods_receipt() -> None:
    gr = GoodsReceipt(
        gr_number="GR-1",
        po_number="PO-1001",
        receipt_date=date(2026, 1, 3),
        lines=[GoodsReceiptLine(line_no=1, description="Widget", quantity_received=Decimal("10"))],
    )
    assert gr.lines[0].quantity_received == Decimal("10")


def test_extra_fields_are_rejected() -> None:
    # extra="forbid" guards against silent schema drift during extraction.
    with pytest.raises(ValidationError):
        LineItem(
            line_no=1,
            description="Widget",
            quantity=Decimal("1"),
            unit_price=Decimal("1"),
            amount=Decimal("1"),
            unexpected_field="boom",  # type: ignore[call-arg]
        )
