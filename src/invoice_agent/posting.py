"""Payment-journal posting (shared by the agent graph, HITL, and the endpoint)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx

from invoice_agent.audit_log import AuditLog, make_audit
from invoice_agent.erp_client import ErpClient
from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DecisionType, Invoice, MatchResult, PaymentJournalEntry

log = get_logger("posting")


class DuplicateJournalError(Exception):
    """The ERP already has a Payment Journal for this invoice (409)."""

    def __init__(self, invoice_number: str, detail: Any) -> None:
        super().__init__(f"Journal already posted for invoice {invoice_number}")
        self.invoice_number = invoice_number
        self.detail = detail


@runtime_checkable
class PaymentPoster(Protocol):
    """Posts an approved invoice as a Payment Journal entry."""

    def post(self, invoice: Invoice, match: MatchResult | None = None) -> PaymentJournalEntry: ...


class ErpPaymentPoster:
    """Posts Payment Journals to the ERP via the HTTP client."""

    def __init__(self, erp: ErpClient) -> None:
        self._erp = erp

    def post(self, invoice: Invoice, match: MatchResult | None = None) -> PaymentJournalEntry:
        payload = {
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "vendor_id": invoice.vendor_id,
            "po_number": invoice.po_number or (match.po_number if match else None),
            "amount": str(invoice.total_amount),
            "currency": invoice.currency,
        }
        return self._erp.post_payment_journal(payload)


class PostingService:
    """Posts a Payment Journal and records the decision to the audit trail.

    Surfaces the ERP's duplicate-posting 409 as :class:`DuplicateJournalError`.
    """

    def __init__(self, poster: PaymentPoster, audit_log: AuditLog | None = None) -> None:
        self._poster = poster
        self._audit = audit_log

    def post(self, invoice: Invoice, match: MatchResult | None = None) -> PaymentJournalEntry:
        try:
            journal = self._poster.post(invoice, match)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == httpx.codes.CONFLICT:
                detail = _safe_json(exc.response)
                log.info("posting.duplicate", invoice_number=invoice.invoice_number)
                raise DuplicateJournalError(invoice.invoice_number, detail) from exc
            raise

        log.info(
            "posting.posted", invoice_number=invoice.invoice_number, journal_id=journal.journal_id
        )
        if self._audit is not None:
            self._audit.record(
                make_audit(
                    invoice.source_email_id or invoice.invoice_number,
                    DecisionType.JOURNAL_POSTED,
                    invoice_number=invoice.invoice_number,
                    source_email_id=invoice.source_email_id,
                    detail={
                        "journal_id": journal.journal_id,
                        "amount": str(journal.amount),
                        "erp_reference": journal.erp_reference,
                    },
                )
            )
        return journal


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:  # pragma: no cover - non-JSON error body
        return response.text
