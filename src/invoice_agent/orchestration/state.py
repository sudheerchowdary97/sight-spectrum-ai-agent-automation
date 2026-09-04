"""Agent graph state and audit-record helper."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from invoice_agent.audit_log import make_audit
from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.schemas import (
    AuditRecord,
    Invoice,
    MatchResult,
    PaymentJournalEntry,
)

__all__ = ["AgentState", "make_audit"]


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
