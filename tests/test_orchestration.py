"""Tests for the agent orchestration node logic (Task 7).

The compiled LangGraph app runs in Docker; here the node functions + router are
driven in the exact order the graph wires them, using fakes — so the full
pipeline logic (extract → match → post/escalate → audit) is verified locally.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.extraction.models import ExtractionResult
from invoice_agent.orchestration.nodes import AgentDeps, AgentNodes, route_after_match
from invoice_agent.orchestration.state import AgentState
from invoice_agent.schemas import (
    DecisionType,
    Invoice,
    LineItem,
    MatchResult,
    MatchStatus,
    MatchType,
    PaymentJournalEntry,
)


def _invoice() -> Invoice:
    return Invoice(
        invoice_id="doc-1",
        invoice_number="90001",
        vendor_name="Acme",
        po_number="PO-1",
        invoice_date=date(2026, 8, 20),
        total_amount=Decimal("25.00"),
        source_email_id="email-1",
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
        dedup_hash="hash-1",
    )


class _FakeExtractor:
    def extract(self, ingested: object) -> ExtractionResult:
        return ExtractionResult(invoice=_invoice(), confidence=1.0, warnings=[])


class _FakeMatcher:
    def __init__(self, status: MatchStatus) -> None:
        self._status = status

    def match_invoice(self, invoice: Invoice) -> MatchResult:
        return MatchResult(
            invoice_number=invoice.invoice_number,
            po_number="PO-1",
            match_type=MatchType.THREE_WAY,
            status=self._status,
            requires_human=self._status is not MatchStatus.MATCHED,
        )


class _FakePoster:
    def post(self, invoice: Invoice, match: MatchResult) -> PaymentJournalEntry:
        return PaymentJournalEntry(
            journal_id="PJ-1",
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            amount=invoice.total_amount,
            posting_date=date(2026, 9, 1),
            erp_reference="ERP-1",
        )


class _Ingested:
    email_id = "email-1"
    document_id = "doc-1"


def _apply(state: AgentState, partial: dict) -> None:
    for key, value in partial.items():
        if key == "audit":
            state["audit"] = state.get("audit", []) + value
        else:
            state[key] = value  # type: ignore[literal-required]


def _run(status: MatchStatus) -> AgentState:
    """Drive the nodes exactly as the graph would."""
    deps = AgentDeps(_FakeExtractor(), _FakeMatcher(status), _FakePoster())
    nodes = AgentNodes(deps)
    state: AgentState = {"ingested": _Ingested(), "correlation_id": "email-1", "audit": []}
    _apply(state, nodes.extract(state))
    _apply(state, nodes.match(state))
    nxt = route_after_match(state)
    _apply(state, (nodes.post if nxt == "post" else nodes.escalate)(state))
    return state


def _decisions(state: AgentState) -> list[str]:
    return [rec.decision.value for rec in state["audit"]]


def test_clean_match_auto_posts() -> None:
    state = _run(MatchStatus.MATCHED)
    assert state["decision"] == "posted"
    assert state["journal"].journal_id == "PJ-1"
    assert _decisions(state) == ["extracted", "matched", "journal_posted"]
    # Every audit record is correlated to the same run and source.
    assert {r.correlation_id for r in state["audit"]} == {"email-1"}


def test_variance_escalates() -> None:
    state = _run(MatchStatus.PRICE_VARIANCE)
    assert state["decision"] == "escalated"
    assert state.get("journal") is None
    assert _decisions(state) == ["extracted", "matched", "exception_raised"]


def test_duplicate_routes_to_escalate_as_duplicate() -> None:
    state = _run(MatchStatus.DUPLICATE)
    assert state["decision"] == "duplicate"
    assert state["audit"][-1].decision is DecisionType.EXCEPTION_RAISED


def test_router() -> None:
    matched: AgentState = {"match": _FakeMatcher(MatchStatus.MATCHED).match_invoice(_invoice())}
    exception: AgentState = {
        "match": _FakeMatcher(MatchStatus.MISSING_PO).match_invoice(_invoice())
    }
    assert route_after_match(matched) == "post"
    assert route_after_match(exception) == "escalate"
