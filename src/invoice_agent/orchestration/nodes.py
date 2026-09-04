"""Agent graph nodes (pure, injectable) and the post-match router.

Each method takes the graph state and returns a partial-state update, so the
whole pipeline can be driven and asserted in tests without LangGraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from invoice_agent.extraction.models import ExtractionResult
from invoice_agent.logging_config import get_logger
from invoice_agent.orchestration.state import AgentState, make_audit
from invoice_agent.posting import PaymentPoster
from invoice_agent.schemas import DecisionType, Invoice, MatchResult, MatchStatus

log = get_logger("agent")


class Extractor(Protocol):
    def extract(self, ingested: object) -> ExtractionResult: ...


class Matcher(Protocol):
    def match_invoice(self, invoice: Invoice) -> MatchResult: ...


@dataclass
class AgentDeps:
    """Services the agent nodes depend on (injectable for tests)."""

    extractor: Extractor
    matcher: Matcher
    poster: PaymentPoster


class AgentNodes:
    """Graph nodes bound to their dependencies."""

    def __init__(self, deps: AgentDeps) -> None:
        self._d = deps

    def extract(self, state: AgentState) -> dict:
        ingested = state["ingested"]
        cid = state["correlation_id"]
        result = self._d.extractor.extract(ingested)
        invoice = result.invoice
        log.info("agent.extracted", correlation_id=cid, invoice_number=invoice.invoice_number)
        rec = make_audit(
            cid,
            DecisionType.EXTRACTED,
            invoice_number=invoice.invoice_number,
            source_email_id=ingested.email_id,
            detail={"confidence": result.confidence, "warnings": result.warnings},
        )
        return {"invoice": invoice, "audit": [rec]}

    def match(self, state: AgentState) -> dict:
        invoice = state["invoice"]
        cid = state["correlation_id"]
        assert invoice is not None
        result = self._d.matcher.match_invoice(invoice)
        log.info("agent.matched", correlation_id=cid, status=result.status.value)
        rec = make_audit(
            cid,
            DecisionType.MATCHED,
            invoice_number=invoice.invoice_number,
            source_email_id=invoice.source_email_id,
            detail={
                "status": result.status.value,
                "po_number": result.po_number,
                "match_type": result.match_type.value,
                "variances": len(result.variances),
            },
        )
        return {"match": result, "audit": [rec]}

    def post(self, state: AgentState) -> dict:
        invoice = state["invoice"]
        match = state["match"]
        cid = state["correlation_id"]
        assert invoice is not None and match is not None
        journal = self._d.poster.post(invoice, match)
        log.info("agent.posted", correlation_id=cid, journal_id=journal.journal_id)
        rec = make_audit(
            cid,
            DecisionType.JOURNAL_POSTED,
            invoice_number=invoice.invoice_number,
            source_email_id=invoice.source_email_id,
            detail={
                "journal_id": journal.journal_id,
                "amount": str(journal.amount),
                "erp_reference": journal.erp_reference,
            },
        )
        return {"journal": journal, "decision": "posted", "audit": [rec]}

    def escalate(self, state: AgentState) -> dict:
        invoice = state["invoice"]
        match = state["match"]
        cid = state["correlation_id"]
        assert invoice is not None and match is not None
        decision = "duplicate" if match.status is MatchStatus.DUPLICATE else "escalated"
        log.info("agent.escalated", correlation_id=cid, status=match.status.value)
        rec = make_audit(
            cid,
            DecisionType.EXCEPTION_RAISED,
            invoice_number=invoice.invoice_number,
            source_email_id=invoice.source_email_id,
            detail={"status": match.status.value, "reason": match.notes or match.status.value},
        )
        return {"decision": decision, "audit": [rec]}


def route_after_match(state: AgentState) -> str:
    """Auto-post a clean match; otherwise route to human escalation."""
    match = state["match"]
    assert match is not None
    return "post" if match.status is MatchStatus.MATCHED else "escalate"
