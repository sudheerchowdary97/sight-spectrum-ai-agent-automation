"""HITL models: the queued exception and approve/reject request bodies."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from invoice_agent.schemas import Invoice, MatchResult, utcnow


class ExceptionStatus(StrEnum):
    """Lifecycle of a queued exception."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExceptionItem(BaseModel):
    """An invoice routed to a human because it could not be auto-processed."""

    exception_id: str
    correlation_id: str | None = None
    invoice: Invoice
    match: MatchResult
    reason: str
    status: ExceptionStatus = ExceptionStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    resolved_by: str | None = None
    resolution_note: str | None = None
    journal_id: str | None = None
    resolved_at: datetime | None = None


class ApproveRequest(BaseModel):
    actor: str = "human"
    note: str | None = None


class RejectRequest(BaseModel):
    actor: str = "human"
    note: str | None = None
