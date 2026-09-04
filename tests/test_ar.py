"""Tests for the AR remittance mirror (Task 10)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from invoice_agent.api.main import create_app
from invoice_agent.ar.service import RemittanceService
from invoice_agent.audit_log import AuditLog
from invoice_agent.schemas import ARItem, DecisionType, Remittance


class _FakeAr:
    """In-memory AR gateway mirroring the mock ERP cash-application logic."""

    def __init__(self, items: list[ARItem]) -> None:
        self._items = {i.ar_item_id: i for i in items}

    def list_ar_items(self, status: str | None = None) -> list[ARItem]:
        return [i for i in self._items.values() if status is None or i.status == status]

    def apply_cash(self, payload: dict[str, Any]) -> dict[str, Any]:
        ar = self._items[payload["ar_item_id"]]
        amount = Decimal(payload["amount"])
        applied = min(amount, ar.open_amount)
        remaining = ar.open_amount - applied
        if amount > ar.open_amount:
            status = "overpaid"
        elif remaining > 0:
            status = "partially_applied"
        else:
            status = "applied"
        self._items[ar.ar_item_id] = ar.model_copy(
            update={"open_amount": remaining, "status": "open" if remaining > 0 else "applied"}
        )
        return {
            "application_id": "CA-1",
            "remittance_id": payload["remittance_id"],
            "ar_item_id": ar.ar_item_id,
            "amount_applied": str(applied),
            "remaining_open": str(remaining),
            "status": status,
        }


def _ar_item(open_amount: str) -> ARItem:
    return ARItem(
        ar_item_id="AR-1",
        customer_id="C-1",
        customer_name="Beta LLC",
        invoice_number="AR-INV-1",
        open_amount=Decimal(open_amount),
    )


def _remittance(amount: str, references: list[str]) -> Remittance:
    return Remittance(
        remittance_id="REM-1",
        customer_name="Beta LLC",
        amount=Decimal(amount),
        references=references,
        remittance_date=date(2026, 9, 1),
        source_email_id="email-rem-1",
    )


def test_full_application() -> None:
    audit = AuditLog()
    service = RemittanceService(_FakeAr([_ar_item("100.00")]), audit)
    result = service.apply(_remittance("100.00", ["AR-INV-1"]))
    assert result.matched is True
    assert result.status == "applied"
    assert result.remaining_open == Decimal("0.00") or result.remaining_open == Decimal("0")
    assert [r.decision for r in audit.list()] == [DecisionType.CASH_APPLIED]


def test_partial_application() -> None:
    service = RemittanceService(_FakeAr([_ar_item("100.00")]))
    result = service.apply(_remittance("40.00", ["AR-INV-1"]))
    assert result.status == "partially_applied"
    assert result.amount_applied == Decimal("40.00")
    assert result.remaining_open == Decimal("60.00")


def test_unmatched_when_reference_not_open() -> None:
    service = RemittanceService(_FakeAr([_ar_item("100.00")]))
    result = service.apply(_remittance("40.00", ["AR-INV-NOPE"]))
    assert result.matched is False
    assert result.status == "unmatched"
    assert result.ar_item_id is None


def test_endpoint_applies_remittance() -> None:
    service = RemittanceService(_FakeAr([_ar_item("100.00")]))
    client = TestClient(create_app(remittance_service=service))
    resp = client.post(
        "/api/v1/apply-remittance",
        json=_remittance("100.00", ["AR-INV-1"]).model_dump(mode="json"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"
    assert resp.json()["ar_item_id"] == "AR-1"
