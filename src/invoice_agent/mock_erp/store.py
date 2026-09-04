"""In-memory ERP data store (Task 2).

Seeded from the Task 1 master JSON files, this is a stand-in for a real ERP.
It is deliberately behind a small interface so a real SAP/Oracle/NetSuite
connector can replace it later without touching the routers.
"""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from invoice_agent.logging_config import get_logger
from invoice_agent.mock_erp.models import (
    CashApplication,
    CashApplicationRequest,
    PaymentJournalRequest,
)
from invoice_agent.schemas import (
    ARItem,
    GoodsReceipt,
    PaymentJournalEntry,
    PurchaseOrder,
)

log = get_logger("mock-erp.store")

TWO_CENTS = Decimal("0.01")


class ERPError(Exception):
    """Base class for ERP domain errors."""


class NotFoundError(ERPError):
    """Requested record does not exist."""


class DuplicateJournalError(ERPError):
    """A Payment Journal already exists for the invoice."""

    def __init__(self, invoice_number: str, existing_journal_id: str) -> None:
        super().__init__(f"Journal already posted for invoice {invoice_number}")
        self.invoice_number = invoice_number
        self.existing_journal_id = existing_journal_id


class ERPStore:
    """Holds ERP master data and records posted journals / cash applications."""

    def __init__(
        self,
        purchase_orders: list[PurchaseOrder] | None = None,
        goods_receipts: list[GoodsReceipt] | None = None,
        ar_items: list[ARItem] | None = None,
    ) -> None:
        self._po: dict[str, PurchaseOrder] = {po.po_number: po for po in (purchase_orders or [])}
        self._gr_by_po: dict[str, list[GoodsReceipt]] = defaultdict(list)
        for gr in goods_receipts or []:
            self._gr_by_po[gr.po_number].append(gr)
        self._ar: dict[str, ARItem] = {ar.ar_item_id: ar for ar in (ar_items or [])}

        self._journals: dict[str, PaymentJournalEntry] = {}
        self._journal_by_invoice: dict[str, str] = {}
        self._cash_apps: dict[str, CashApplication] = {}
        self._journal_seq = itertools.count(1)
        self._cash_seq = itertools.count(1)

    # ------------------------------------------------------------------ loading
    @classmethod
    def from_dir(cls, data_dir: str | Path) -> ERPStore:
        """Build a store from Task 1 master JSON files. Missing files → empty."""
        path = Path(data_dir)

        def _load(name: str) -> list[dict]:
            file = path / name
            if not file.exists():
                log.warning("erp.seed.missing", file=str(file))
                return []
            return json.loads(file.read_text(encoding="utf-8"))

        store = cls(
            purchase_orders=[
                PurchaseOrder.model_validate(d) for d in _load("purchase_orders.json")
            ],
            goods_receipts=[GoodsReceipt.model_validate(d) for d in _load("goods_receipts.json")],
            ar_items=[ARItem.model_validate(d) for d in _load("ar_items.json")],
        )
        log.info(
            "erp.seed.loaded",
            purchase_orders=len(store._po),
            ar_items=len(store._ar),
            data_dir=str(path),
        )
        return store

    # ------------------------------------------------------------------- reads
    def get_purchase_order(self, po_number: str) -> PurchaseOrder:
        po = self._po.get(po_number)
        if po is None:
            raise NotFoundError(f"Purchase order {po_number} not found")
        return po

    def get_goods_receipts(self, po_number: str) -> list[GoodsReceipt]:
        return list(self._gr_by_po.get(po_number, []))

    def list_ar_items(self, status: str | None = None) -> list[ARItem]:
        items = list(self._ar.values())
        if status is not None:
            items = [ar for ar in items if ar.status == status]
        return items

    def get_ar_item(self, ar_item_id: str) -> ARItem:
        ar = self._ar.get(ar_item_id)
        if ar is None:
            raise NotFoundError(f"AR item {ar_item_id} not found")
        return ar

    def list_journals(self) -> list[PaymentJournalEntry]:
        return list(self._journals.values())

    def get_journal(self, journal_id: str) -> PaymentJournalEntry:
        entry = self._journals.get(journal_id)
        if entry is None:
            raise NotFoundError(f"Journal {journal_id} not found")
        return entry

    # ------------------------------------------------------------------ writes
    def post_journal(self, req: PaymentJournalRequest) -> PaymentJournalEntry:
        """Post a Payment Journal. Idempotent per invoice → raises on duplicate."""
        existing_id = self._journal_by_invoice.get(req.invoice_number)
        if existing_id is not None:
            raise DuplicateJournalError(req.invoice_number, existing_id)

        seq = next(self._journal_seq)
        entry = PaymentJournalEntry(
            journal_id=f"PJ-{seq:06d}",
            invoice_number=req.invoice_number,
            po_number=req.po_number,
            vendor_id=req.vendor_id,
            vendor_name=req.vendor_name,
            amount=req.amount,
            currency=req.currency,
            gl_account=req.gl_account,
            posting_date=req.posting_date or date.today(),
            status="posted",
            erp_reference=f"ERP-DOC-{seq:06d}",
        )
        self._journals[entry.journal_id] = entry
        self._journal_by_invoice[req.invoice_number] = entry.journal_id
        log.info("erp.journal.posted", journal_id=entry.journal_id, invoice=req.invoice_number)
        return entry

    def apply_cash(self, req: CashApplicationRequest) -> CashApplication:
        """Apply a remittance to an open AR item, reducing its open amount."""
        ar = self.get_ar_item(req.ar_item_id)  # raises NotFoundError

        applied = min(req.amount, ar.open_amount)
        remaining = (ar.open_amount - applied).quantize(TWO_CENTS)
        if req.amount > ar.open_amount:
            status = "overpaid"
        elif remaining > 0:
            status = "partially_applied"
        else:
            status = "applied"

        self._ar[ar.ar_item_id] = ar.model_copy(
            update={"open_amount": remaining, "status": "open" if remaining > 0 else "applied"}
        )

        seq = next(self._cash_seq)
        application = CashApplication(
            application_id=f"CA-{seq:06d}",
            remittance_id=req.remittance_id,
            ar_item_id=req.ar_item_id,
            amount_applied=applied,
            remaining_open=remaining,
            status=status,
        )
        self._cash_apps[application.application_id] = application
        log.info(
            "erp.cash.applied",
            application_id=application.application_id,
            ar_item=req.ar_item_id,
            status=status,
        )
        return application
