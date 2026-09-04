"""In-memory audit log and the audit-record factory.

Every agent/human decision is recorded here, correlated by ``correlation_id``
and traceable to the source email — the backbone of the auditability
requirement. Task 11 exposes this via ``GET /api/v1/audit-log``.
"""

from __future__ import annotations

import uuid
from typing import Any

from invoice_agent.schemas import AuditRecord, DecisionType


def make_audit(
    correlation_id: str,
    decision: DecisionType,
    *,
    invoice_number: str | None,
    source_email_id: str | None,
    detail: dict[str, Any],
    actor: str = "agent",
) -> AuditRecord:
    """Build an audit record linking a decision to its source."""
    return AuditRecord(
        record_id=uuid.uuid4().hex[:12],
        correlation_id=correlation_id,
        decision=decision,
        actor=actor,
        invoice_number=invoice_number,
        source_email_id=source_email_id,
        detail=detail,
    )


class AuditLog:
    """Append-only in-memory audit trail."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(self, record: AuditRecord) -> None:
        self._records.append(record)

    def list(
        self, *, correlation_id: str | None = None, invoice_number: str | None = None
    ) -> list[AuditRecord]:
        records = self._records
        if correlation_id is not None:
            records = [r for r in records if r.correlation_id == correlation_id]
        if invoice_number is not None:
            records = [r for r in records if r.invoice_number == invoice_number]
        return list(records)
