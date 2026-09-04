"""Matching service: resolve PO (number or RAG) + GR, dedup, run the engine."""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger
from invoice_agent.matching import engine
from invoice_agent.matching.dedup import DedupStore
from invoice_agent.matching.gateway import PoGateway
from invoice_agent.matching.tolerances import ToleranceProvider
from invoice_agent.schemas import Invoice, MatchResult, MatchStatus, MatchType, PurchaseOrder

log = get_logger("matching")


class MatchService:
    """Orchestrates PO/GR resolution and the matching engine for one invoice."""

    def __init__(
        self,
        erp: PoGateway,
        tolerances: ToleranceProvider,
        dedup: DedupStore | None = None,
        rag: object | None = None,
        reviewer: object | None = None,
    ) -> None:
        self._erp = erp
        self._tolerances = tolerances
        self._dedup = dedup or DedupStore()
        self._rag = rag  # RagService | None (kept loose to avoid a hard import)
        self._reviewer = reviewer  # hitl.Reviewer | None

    def match_invoice(self, invoice: Invoice) -> MatchResult:
        # 1) Duplicate detection (content hash from extraction).
        if self._dedup.seen(invoice.dedup_hash):
            log.info("match.duplicate", invoice_number=invoice.invoice_number)
            return self._finalize(
                invoice,
                MatchResult(
                    invoice_number=invoice.invoice_number,
                    po_number=invoice.po_number,
                    match_type=MatchType.TWO_WAY,
                    status=MatchStatus.DUPLICATE,
                    requires_human=True,
                    notes="Duplicate invoice (content already seen)",
                ),
            )
        self._dedup.add(invoice.dedup_hash)

        # 2) Resolve the PO — by number first, then RAG retrieval as a fallback.
        purchase_order = self._resolve_po(invoice)

        # 3) Pull the Goods Receipt (enables the 3-way match).
        goods_receipt = None
        if purchase_order is not None:
            receipts = self._erp.get_goods_receipts(purchase_order.po_number)
            goods_receipt = receipts[0] if receipts else None

        tolerances = self._tolerances.for_vendor(
            purchase_order.vendor_id if purchase_order else None
        )
        result = engine.match(invoice, purchase_order, goods_receipt, tolerances)
        log.info(
            "match.done",
            invoice_number=invoice.invoice_number,
            po_number=result.po_number,
            status=result.status.value,
            match_type=result.match_type.value,
        )
        return self._finalize(invoice, result)

    def _finalize(self, invoice: Invoice, result: MatchResult) -> MatchResult:
        """Queue an exception for human review when the match needs oversight."""
        if self._reviewer is not None and result.requires_human:
            try:
                self._reviewer.submit(invoice, result)
            except Exception as exc:  # pragma: no cover - queueing is best-effort
                log.info("match.review_submit_error", error=str(exc))
        return result

    def _resolve_po(self, invoice: Invoice) -> PurchaseOrder | None:
        if invoice.po_number:
            po = self._erp.get_purchase_order(invoice.po_number)
            if po is not None:
                return po

        # Fall back to semantic retrieval (handles wrong/missing PO numbers).
        if self._rag is not None:
            try:
                candidates = self._rag.find_candidate_pos(invoice, top_k=1)
            except Exception as exc:  # pragma: no cover - retrieval is best-effort
                log.info("match.rag_error", error=str(exc))
                candidates = []
            if candidates:
                return self._erp.get_purchase_order(candidates[0].po_number)
        return None


def build_match_service(settings: Settings, reviewer: object | None = None) -> MatchService:
    """Build the real matching service (HTTP ERP client + RAG + tolerances)."""
    from invoice_agent.erp_client import ErpClient
    from invoice_agent.rag.service import build_rag_service

    return MatchService(
        erp=ErpClient(settings.erp_base_url),
        tolerances=ToleranceProvider.from_settings(settings),
        dedup=DedupStore(),
        rag=build_rag_service(settings),
        reviewer=reviewer,
    )
