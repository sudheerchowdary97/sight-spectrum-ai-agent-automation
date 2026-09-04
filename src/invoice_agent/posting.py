"""Payment-journal posting (shared by the agent graph and the Task 9 endpoint)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_agent.erp_client import ErpClient
from invoice_agent.schemas import Invoice, MatchResult, PaymentJournalEntry


@runtime_checkable
class PaymentPoster(Protocol):
    """Posts an approved invoice as a Payment Journal entry."""

    def post(self, invoice: Invoice, match: MatchResult) -> PaymentJournalEntry: ...


class ErpPaymentPoster:
    """Posts Payment Journals to the ERP via the HTTP client."""

    def __init__(self, erp: ErpClient) -> None:
        self._erp = erp

    def post(self, invoice: Invoice, match: MatchResult) -> PaymentJournalEntry:
        payload = {
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "vendor_id": invoice.vendor_id,
            "po_number": invoice.po_number or match.po_number,
            "amount": str(invoice.total_amount),
            "currency": invoice.currency,
        }
        return self._erp.post_payment_journal(payload)
