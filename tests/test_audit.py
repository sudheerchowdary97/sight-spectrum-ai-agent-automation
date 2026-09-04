"""Tests for the audit-log endpoint (Task 11)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from invoice_agent.api.main import create_app
from invoice_agent.audit_log import AuditLog, make_audit
from invoice_agent.schemas import DecisionType


def _audit_log() -> AuditLog:
    log = AuditLog()
    log.record(
        make_audit(
            "corr-1",
            DecisionType.EXTRACTED,
            invoice_number="90001",
            source_email_id="email-1",
            detail={},
        )
    )
    log.record(
        make_audit(
            "corr-1",
            DecisionType.MATCHED,
            invoice_number="90001",
            source_email_id="email-1",
            detail={"status": "matched"},
        )
    )
    log.record(
        make_audit(
            "corr-2",
            DecisionType.EXCEPTION_RAISED,
            invoice_number="90004",
            source_email_id="email-4",
            detail={},
        )
    )
    return log


def _client() -> TestClient:
    return TestClient(create_app(audit_log=_audit_log()))


def test_audit_log_returns_all() -> None:
    resp = _client().get("/api/v1/audit-log")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_audit_log_filter_by_correlation_id() -> None:
    resp = _client().get("/api/v1/audit-log", params={"correlation_id": "corr-1"})
    body = resp.json()
    assert len(body) == 2
    assert {r["decision"] for r in body} == {"extracted", "matched"}
    # Provenance: each record ties back to its source email.
    assert all(r["source_email_id"] == "email-1" for r in body)


def test_audit_log_filter_by_invoice_and_limit() -> None:
    resp = _client().get("/api/v1/audit-log", params={"invoice_number": "90001", "limit": 1})
    body = resp.json()
    assert len(body) == 1
    assert body[0]["decision"] == "matched"  # newest of the two
