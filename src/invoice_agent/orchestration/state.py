"""Agent graph state and audit-record helper."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, TypedDict

from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.schemas import (
    AuditRecord,
    DecisionType,
    Invoice,
    MatchResult,
    PaymentJournalEntry,
)


class AgentState(TypedDict, total=False):
    """State threaded through the agent graph.

    ``audit`` uses an additive reducer so each node appends its own record(s).
    """

    ingested: IngestedDocument
    correlation_id: str
    invoice: Invoice | None
    match: MatchResult | None
    journal: PaymentJournalEntry | None
    decision: str
    audit: Annotated[list[AuditRecord], operator.add]
    error: str | None


def make_audit(
    correlation_id: str,
    decision: DecisionType,
    *,
    invoice_number: str | None,
    source_email_id: str | None,
    detail: dict[str, Any],
    actor: str = "agent",
) -> AuditRecord:
    """Build an audit record linking a decision to its source."""
    return AuditRecord(
        record_id=uuid.uuid4().hex[:12],
        correlation_id=correlation_id,
        decision=decision,
        actor=actor,
        invoice_number=invoice_number,
        source_email_id=source_email_id,
        detail=detail,
    )
