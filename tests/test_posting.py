"""Tests for payment-journal posting (Task 9)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from invoice_agent.api.main import create_app
from invoice_agent.audit_log import AuditLog
from invoice_agent.posting import DuplicateJournalError, PostingService
from invoice_agent.schemas import (
    DecisionType,
    Invoice,
    LineItem,
    MatchResult,
    PaymentJournalEntry,
)


def _invoice() -> Invoice:
    return Invoice(
        invoice_id="doc-1",
        invoice_number="90005",
        vendor_name="Acme",
        po_number="PO-10005",
        invoice_date=date(2026, 8, 26),
        total_amount=Decimal("349.00"),
        source_email_id="email-5",
        lines=[
            LineItem(
                line_no=1,
                sku="SKU-1",
                description="Stapler",
                quantity=Decimal("25"),
                unit_price=Decimal("13.96"),
                amount=Decimal("349.00"),
            )
        ],
    )


class _OkPoster:
    def post(self, invoice: Invoice, match: MatchResult | None = None) -> PaymentJournalEntry:
        return PaymentJournalEntry(
            journal_id="PJ-1",
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            amount=invoice.total_amount,
            posting_date=date(2026, 9, 1),
            erp_reference="ERP-1",
        )


class _DuplicatePoster:
    def post(self, invoice: Invoice, match: MatchResult | None = None) -> PaymentJournalEntry:
        request = httpx.Request("POST", "http://erp/api/v1/payment-journals")
        response = httpx.Response(409, request=request, json={"existing_journal_id": "PJ-0"})
        raise httpx.HTTPStatusError("conflict", request=request, response=response)


def test_posting_service_posts_and_audits() -> None:
    audit = AuditLog()
    journal = PostingService(_OkPoster(), audit).post(_invoice())
    assert journal.journal_id == "PJ-1"
    assert [r.decision for r in audit.list()] == [DecisionType.JOURNAL_POSTED]


def test_posting_service_maps_duplicate_to_domain_error() -> None:
    with pytest.raises(DuplicateJournalError) as excinfo:
        PostingService(_DuplicatePoster()).post(_invoice())
    assert excinfo.value.invoice_number == "90005"


def test_endpoint_posts_and_conflicts() -> None:
    ok = TestClient(create_app(posting_service=PostingService(_OkPoster())))
    resp = ok.post("/api/v1/post-payment-journal", json=_invoice().model_dump(mode="json"))
    assert resp.status_code == 201
    assert resp.json()["journal_id"] == "PJ-1"

    dup = TestClient(create_app(posting_service=PostingService(_DuplicatePoster())))
    resp = dup.post("/api/v1/post-payment-journal", json=_invoice().model_dump(mode="json"))
    assert resp.status_code == 409
    assert resp.json()["detail"]["invoice_number"] == "90005"
