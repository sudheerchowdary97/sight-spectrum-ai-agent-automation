"""Human review service: submit exceptions, then approve (→ post) or reject."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_agent.audit_log import AuditLog, make_audit
from invoice_agent.hitl.models import ExceptionItem, ExceptionStatus
from invoice_agent.hitl.store import ExceptionStore
from invoice_agent.logging_config import get_logger
from invoice_agent.posting import PaymentPoster
from invoice_agent.schemas import DecisionType, Invoice, MatchResult, utcnow

log = get_logger("hitl")


class ReviewError(Exception):
    """Base class for review errors."""


class NotFoundError(ReviewError):
    """Exception id not found."""


class AlreadyResolvedError(ReviewError):
    """Exception has already been approved or rejected."""


@runtime_checkable
class Reviewer(Protocol):
    """Something that can queue an exception for human review."""

    def submit(
        self, invoice: Invoice, match: MatchResult, correlation_id: str | None = None
    ) -> ExceptionItem: ...


class HumanReviewService:
    """Queue exceptions and resolve them (approve posts the journal)."""

    def __init__(
        self, store: ExceptionStore, poster: PaymentPoster, audit_log: AuditLog | None = None
    ) -> None:
        self._store = store
        self._poster = poster
        self._audit = audit_log

    # ---------------------------------------------------------------- queue
    def submit(
        self, invoice: Invoice, match: MatchResult, correlation_id: str | None = None
    ) -> ExceptionItem:
        item = self._store.add(invoice, match, correlation_id or invoice.source_email_id)
        log.info("hitl.submitted", exception_id=item.exception_id, reason=item.reason)
        self._audit_record(
            item,
            DecisionType.EXCEPTION_RAISED,
            actor="agent",
            detail={
                "exception_id": item.exception_id,
                "status": match.status.value,
            },
        )
        return item

    def list(self, status: ExceptionStatus | None = None) -> list[ExceptionItem]:
        return self._store.list(status)

    def get(self, exception_id: str) -> ExceptionItem:
        item = self._store.get(exception_id)
        if item is None:
            raise NotFoundError(f"Exception {exception_id} not found")
        return item

    # ------------------------------------------------------------- resolve
    def approve(
        self, exception_id: str, actor: str = "human", note: str | None = None
    ) -> ExceptionItem:
        item = self._require_pending(exception_id)
        journal = self._poster.post(item.invoice, item.match)
        item.status = ExceptionStatus.APPROVED
        item.resolved_by = actor
        item.resolution_note = note
        item.journal_id = journal.journal_id
        item.resolved_at = utcnow()
        self._store.save(item)
        log.info(
            "hitl.approved", exception_id=exception_id, journal_id=journal.journal_id, actor=actor
        )
        self._audit_record(
            item,
            DecisionType.HUMAN_APPROVED,
            actor=f"human:{actor}",
            detail={
                "exception_id": exception_id,
                "note": note,
            },
        )
        self._audit_record(
            item,
            DecisionType.JOURNAL_POSTED,
            actor=f"human:{actor}",
            detail={
                "journal_id": journal.journal_id,
                "amount": str(journal.amount),
            },
        )
        return item

    def reject(
        self, exception_id: str, actor: str = "human", note: str | None = None
    ) -> ExceptionItem:
        item = self._require_pending(exception_id)
        item.status = ExceptionStatus.REJECTED
        item.resolved_by = actor
        item.resolution_note = note
        item.resolved_at = utcnow()
        self._store.save(item)
        log.info("hitl.rejected", exception_id=exception_id, actor=actor)
        self._audit_record(
            item,
            DecisionType.HUMAN_REJECTED,
            actor=f"human:{actor}",
            detail={
                "exception_id": exception_id,
                "note": note,
            },
        )
        return item

    # ------------------------------------------------------------ internals
    def _require_pending(self, exception_id: str) -> ExceptionItem:
        item = self.get(exception_id)
        if item.status is not ExceptionStatus.PENDING:
            raise AlreadyResolvedError(f"Exception {exception_id} already {item.status.value}")
        return item

    def _audit_record(
        self, item: ExceptionItem, decision: DecisionType, *, actor: str, detail: dict
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            make_audit(
                item.correlation_id or item.invoice.invoice_number,
                decision,
                invoice_number=item.invoice.invoice_number,
                source_email_id=item.invoice.source_email_id,
                detail=detail,
                actor=actor,
            )
        )
