"""Tests for human-in-the-loop exception review (Task 8)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from invoice_agent.api.main import create_app
from invoice_agent.audit_log import AuditLog
from invoice_agent.hitl.service import (
    AlreadyResolvedError,
    HumanReviewService,
    NotFoundError,
)
from invoice_agent.hitl.store import ExceptionStore
from invoice_agent.matching.dedup import DedupStore
from invoice_agent.matching.service import MatchService
from invoice_agent.matching.tolerances import ToleranceProvider, Tolerances
from invoice_agent.schemas import (
    DecisionType,
    GoodsReceipt,
    Invoice,
    LineItem,
    MatchResult,
    MatchStatus,
    MatchType,
    PaymentJournalEntry,
    PurchaseOrder,
)

TOL = Tolerances(
    price_tolerance_pct=0.02, qty_tolerance_pct=0.0, amount_tolerance_abs=Decimal("1.00")
)


def _invoice() -> Invoice:
    return Invoice(
        invoice_id="doc-1",
        invoice_number="90004",
        vendor_name="Acme",
        po_number="PO-1",
        invoice_date=date(2026, 8, 20),
        total_amount=Decimal("30.00"),
        source_email_id="email-4",
        lines=[
            LineItem(
                line_no=1,
                sku="SKU-1",
                description="Widget",
                quantity=Decimal("12"),
                unit_price=Decimal("2.50"),
                amount=Decimal("30.00"),
            )
        ],
        dedup_hash="hash-4",
    )


def _variance_match() -> MatchResult:
    return MatchResult(
        invoice_number="90004",
        po_number="PO-1",
        match_type=MatchType.THREE_WAY,
        status=MatchStatus.QTY_VARIANCE,
        requires_human=True,
        notes="qty variance",
    )


class _FakePoster:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, invoice: Invoice, match: MatchResult) -> PaymentJournalEntry:
        self.calls += 1
        return PaymentJournalEntry(
            journal_id="PJ-9",
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            amount=invoice.total_amount,
            posting_date=date(2026, 9, 1),
            erp_reference="ERP-9",
        )


def _service() -> tuple[HumanReviewService, _FakePoster, AuditLog]:
    poster = _FakePoster()
    audit = AuditLog()
    return HumanReviewService(ExceptionStore(), poster, audit), poster, audit


def test_submit_queues_pending_and_audits() -> None:
    service, _poster, audit = _service()
    item = service.submit(_invoice(), _variance_match(), correlation_id="email-4")
    assert item.status.value == "pending"
    assert service.list() == [item]
    assert [r.decision for r in audit.list()] == [DecisionType.EXCEPTION_RAISED]


def test_approve_posts_journal_and_audits() -> None:
    service, poster, audit = _service()
    item = service.submit(_invoice(), _variance_match())
    resolved = service.approve(item.exception_id, actor="alice", note="ok to pay")

    assert resolved.status.value == "approved"
    assert resolved.journal_id == "PJ-9"
    assert resolved.resolved_by == "alice"
    assert poster.calls == 1
    decisions = [r.decision for r in audit.list()]
    assert DecisionType.HUMAN_APPROVED in decisions
    assert DecisionType.JOURNAL_POSTED in decisions


def test_reject_closes_without_posting() -> None:
    service, poster, audit = _service()
    item = service.submit(_invoice(), _variance_match())
    resolved = service.reject(item.exception_id, actor="bob", note="wrong price")
    assert resolved.status.value == "rejected"
    assert poster.calls == 0
    assert DecisionType.HUMAN_REJECTED in [r.decision for r in audit.list()]


def test_double_resolution_conflicts() -> None:
    service, _poster, _audit = _service()
    item = service.submit(_invoice(), _variance_match())
    service.approve(item.exception_id)
    with pytest.raises(AlreadyResolvedError):
        service.approve(item.exception_id)


def test_get_unknown_raises() -> None:
    service, _poster, _audit = _service()
    with pytest.raises(NotFoundError):
        service.get("EXC-999999")


# --- MatchService queues an exception when a review is required ---
class _MissingPoGateway:
    def get_purchase_order(self, po_number: str) -> PurchaseOrder | None:
        return None

    def get_goods_receipts(self, po_number: str) -> list[GoodsReceipt]:
        return []


def test_match_service_submits_exception_on_requires_human() -> None:
    review, _poster, _audit = _service()
    match_service = MatchService(
        erp=_MissingPoGateway(),
        tolerances=ToleranceProvider(TOL),
        dedup=DedupStore(),
        rag=None,
        reviewer=review,
    )
    result = match_service.match_invoice(_invoice())
    assert result.status is MatchStatus.MISSING_PO
    pending = review.list()
    assert len(pending) == 1
    assert pending[0].invoice.invoice_number == "90004"


# --- Endpoint flow: list → approve ---
def test_exception_endpoints_approve_flow() -> None:
    review, _poster, _audit = _service()
    item = review.submit(_invoice(), _variance_match())
    client = TestClient(create_app(review_service=review))

    listed = client.get("/api/v1/exceptions", params={"status": "pending"}).json()
    assert len(listed) == 1 and listed[0]["exception_id"] == item.exception_id

    resp = client.post(f"/api/v1/exceptions/{item.exception_id}/approve", json={"actor": "carol"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["journal_id"] == "PJ-9"

    # Second approval conflicts.
    assert client.post(f"/api/v1/exceptions/{item.exception_id}/approve").status_code == 409
