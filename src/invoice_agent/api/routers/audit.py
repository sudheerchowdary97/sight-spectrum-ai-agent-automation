"""Audit-log endpoint (GET /api/v1/audit-log).

Exposes the decision trail — every agent/human decision, correlated and
traceable to its source email (the auditability requirement).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from invoice_agent.audit_log import AuditLog
from invoice_agent.schemas import AuditRecord

router = APIRouter(tags=["audit"])


def get_audit_log(request: Request) -> AuditLog:
    return request.app.state.audit_log


@router.get(
    "/audit-log",
    response_model=list[AuditRecord],
    summary="Retrieve the decision audit trail",
)
def get_audit_log_records(
    correlation_id: str | None = Query(default=None, description="Filter by run correlation id"),
    invoice_number: str | None = Query(default=None, description="Filter by invoice number"),
    limit: int | None = Query(default=None, ge=1, description="Return only the most recent N"),
    audit: AuditLog = Depends(get_audit_log),
) -> list[AuditRecord]:
    """Return audit records, newest last, optionally filtered."""
    records = audit.list(correlation_id=correlation_id, invoice_number=invoice_number)
    if limit is not None:
        records = records[-limit:]
    return records
