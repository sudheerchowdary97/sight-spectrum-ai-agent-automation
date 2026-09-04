"""Remittance service: match a remittance to an open AR item and apply cash."""

from __future__ import annotations

from decimal import Decimal

from invoice_agent.ar.models import ArGateway, RemittanceResult
from invoice_agent.audit_log import AuditLog, make_audit
from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import ARItem, DecisionType, Remittance

log = get_logger("ar")


class RemittanceService:
    """Applies inbound remittances against open AR items."""

    def __init__(self, erp: ArGateway, audit_log: AuditLog | None = None) -> None:
        self._erp = erp
        self._audit = audit_log

    def apply(self, remittance: Remittance) -> RemittanceResult:
        target = self._find_open_item(remittance)
        if target is None:
            log.info("ar.unmatched", remittance_id=remittance.remittance_id)
            return RemittanceResult(
                remittance_id=remittance.remittance_id, matched=False, status="unmatched"
            )

        application = self._erp.apply_cash(
            {
                "remittance_id": remittance.remittance_id,
                "ar_item_id": target.ar_item_id,
                "amount": str(remittance.amount),
                "currency": remittance.currency,
            }
        )
        log.info(
            "ar.applied",
            remittance_id=remittance.remittance_id,
            ar_item_id=target.ar_item_id,
            status=application["status"],
        )
        self._record_audit(remittance, target, application)
        return RemittanceResult(
            remittance_id=remittance.remittance_id,
            matched=True,
            status=application["status"],
            ar_item_id=target.ar_item_id,
            application_id=application.get("application_id"),
            amount_applied=Decimal(str(application["amount_applied"])),
            remaining_open=Decimal(str(application["remaining_open"])),
        )

    def _find_open_item(self, remittance: Remittance) -> ARItem | None:
        open_items = self._erp.list_ar_items("open")
        by_invoice = {item.invoice_number: item for item in open_items}
        for reference in remittance.references:
            if reference in by_invoice:
                return by_invoice[reference]
        return None

    def _record_audit(self, remittance: Remittance, target: ARItem, application: dict) -> None:
        if self._audit is None:
            return
        self._audit.record(
            make_audit(
                remittance.source_email_id or remittance.remittance_id,
                DecisionType.CASH_APPLIED,
                invoice_number=target.invoice_number,
                source_email_id=remittance.source_email_id,
                detail={
                    "remittance_id": remittance.remittance_id,
                    "ar_item_id": target.ar_item_id,
                    "amount_applied": str(application["amount_applied"]),
                    "remaining_open": str(application["remaining_open"]),
                    "status": application["status"],
                },
            )
        )


def build_remittance_service(
    settings: Settings, audit_log: AuditLog | None = None
) -> RemittanceService:
    """Build the real remittance service backed by the ERP HTTP client."""
    from invoice_agent.erp_client import ErpClient

    return RemittanceService(ErpClient(settings.erp_base_url), audit_log)
