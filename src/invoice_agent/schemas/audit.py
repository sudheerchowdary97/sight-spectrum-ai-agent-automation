"""Matching results and the audit trail (Tasks 6, 8, 11).

The :class:`AuditRecord` is the backbone of the auditability requirement: every
decision the agent (or a human) makes is written as one record, correlated by
``correlation_id`` and traceable back to the source email.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from invoice_agent.schemas.common import DomainModel, MatchStatus, MatchType, utcnow


class Variance(DomainModel):
    """A single detected discrepancy during matching."""

    field: str  # e.g. "unit_price", "quantity", "total_amount"
    line_no: int | None = None
    expected: str  # value from PO / GR
    actual: str  # value from invoice
    delta_pct: float | None = None
    within_tolerance: bool


class MatchResult(DomainModel):
    """Outcome of matching an invoice against a PO (and optionally a GR)."""

    invoice_number: str
    po_number: str | None = None
    gr_number: str | None = None
    match_type: MatchType
    status: MatchStatus
    variances: list[Variance] = Field(default_factory=list)
    confidence: float | None = None
    requires_human: bool = False
    notes: str | None = None


class DecisionType(StrEnum):
    """The kind of decision captured in an audit record."""

    INGESTED = "ingested"
    EXTRACTED = "extracted"
    MATCHED = "matched"
    EXCEPTION_RAISED = "exception_raised"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    JOURNAL_POSTED = "journal_posted"
    CASH_APPLIED = "cash_applied"


class AuditRecord(DomainModel):
    """An immutable log of one decision, linked to its source and payload."""

    record_id: str
    correlation_id: str  # groups all records for one invoice/remittance run
    decision: DecisionType
    actor: str = "agent"  # "agent" or "human:<user-id>"

    invoice_number: str | None = None
    source_email_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utcnow)
