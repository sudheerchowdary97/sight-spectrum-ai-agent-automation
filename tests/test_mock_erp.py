"""Tests for the Mock ERP service (Task 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from invoice_agent.mock_erp.main import create_app
from invoice_agent.mock_erp.store import ERPStore
from invoice_agent.schemas import (
    ARItem,
    GoodsReceipt,
    GoodsReceiptLine,
    LineItem,
    PurchaseOrder,
)


def _store() -> ERPStore:
    po = PurchaseOrder(
        po_number="PO-10001",
        vendor_id="V-1001",
        vendor_name="Acme Corp",
        order_date=date(2026, 8, 1),
        lines=[
            LineItem(
                line_no=1,
                sku="SKU-1",
                description="Widget",
                quantity=Decimal("10"),
                unit_price=Decimal("2.50"),
                amount=Decimal("25.00"),
            )
        ],
        total_amount=Decimal("25.00"),
    )
    gr = GoodsReceipt(
        gr_number="GR-5001",
        po_number="PO-10001",
        receipt_date=date(2026, 8, 3),
        lines=[
            GoodsReceiptLine(
                line_no=1, sku="SKU-1", description="Widget", quantity_received=Decimal("10")
            )
        ],
    )
    ar = ARItem(
        ar_item_id="AR-7001",
        customer_id="C-2001",
        customer_name="Beta LLC",
        invoice_number="AR-INV-40001",
        open_amount=Decimal("100.00"),
    )
    return ERPStore(purchase_orders=[po], goods_receipts=[gr], ar_items=[ar])


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(store=_store()))


def test_get_purchase_order(client: TestClient) -> None:
    resp = client.get("/api/v1/purchase-orders/PO-10001")
    assert resp.status_code == 200
    assert resp.json()["total_amount"] == "25.00"

    assert client.get("/api/v1/purchase-orders/PO-DOESNOTEXIST").status_code == 404


def test_goods_receipts(client: TestClient) -> None:
    resp = client.get("/api/v1/goods-receipts", params={"po_number": "PO-10001"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1 and body[0]["gr_number"] == "GR-5001"


def test_list_ar_items_filter(client: TestClient) -> None:
    assert len(client.get("/api/v1/ar-items").json()) == 1
    assert len(client.get("/api/v1/ar-items", params={"status": "open"}).json()) == 1
    assert client.get("/api/v1/ar-items", params={"status": "applied"}).json() == []


def test_post_journal_and_duplicate(client: TestClient) -> None:
    payload = {
        "invoice_number": "90001",
        "vendor_name": "Acme Corp",
        "po_number": "PO-10001",
        "amount": "25.00",
        "posting_date": "2026-09-01",
    }
    first = client.post("/api/v1/payment-journals", json=payload)
    assert first.status_code == 201
    journal_id = first.json()["journal_id"]
    assert first.json()["erp_reference"]

    # Second post for the same invoice is a conflict.
    dup = client.post("/api/v1/payment-journals", json=payload)
    assert dup.status_code == 409
    assert dup.json()["detail"]["existing_journal_id"] == journal_id

    listed = client.get("/api/v1/payment-journals").json()
    assert len(listed) == 1
    assert client.get(f"/api/v1/payment-journals/{journal_id}").status_code == 200


def test_cash_application_full_and_partial(client: TestClient) -> None:
    # Partial application first.
    partial = client.post(
        "/api/v1/cash-applications",
        json={"remittance_id": "REM-1", "ar_item_id": "AR-7001", "amount": "40.00"},
    )
    assert partial.status_code == 201
    assert partial.json()["status"] == "partially_applied"
    assert partial.json()["remaining_open"] == "60.00"

    # Remaining 60 now fully applied.
    full = client.post(
        "/api/v1/cash-applications",
        json={"remittance_id": "REM-2", "ar_item_id": "AR-7001", "amount": "60.00"},
    )
    assert full.status_code == 201
    assert full.json()["status"] == "applied"
    assert full.json()["remaining_open"] == "0.00"

    # Unknown AR item → 404.
    missing = client.post(
        "/api/v1/cash-applications",
        json={"remittance_id": "REM-3", "ar_item_id": "AR-NOPE", "amount": "1.00"},
    )
    assert missing.status_code == 404
