"""Tests for evaluation metrics and report (Task 13)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_agent.evaluation.metrics import (
    aggregate_extraction,
    compare_extraction,
    invoice_to_fields,
    match_metrics,
    retrieval_metrics,
)
from invoice_agent.evaluation.report import EvaluationReport
from invoice_agent.schemas import Invoice, LineItem


def _invoice() -> Invoice:
    return Invoice(
        invoice_id="i1",
        invoice_number="90005",
        vendor_name="Collins, Carney and Santos",
        po_number="PO-10005",
        invoice_date=date(2026, 8, 26),
        total_amount=Decimal("349.00"),
        lines=[
            LineItem(
                line_no=1,
                sku="SKU-1003",
                description="Stapler",
                quantity=Decimal("25"),
                unit_price=Decimal("13.96"),
                amount=Decimal("349.00"),
            )
        ],
    )


def test_compare_extraction_typed_equality() -> None:
    expected = {
        "invoice_number": "90005",
        "vendor_name": "COLLINS, CARNEY AND SANTOS",  # case-insensitive
        "total_amount": "349",  # 349 == 349.00
        "po_number": "PO-10005",
        "line_count": 1,
    }
    results = compare_extraction(expected, invoice_to_fields(_invoice()))
    assert results == {
        "invoice_number": True,
        "vendor_name": True,
        "total_amount": True,
        "po_number": True,
        "line_count": True,
    }


def test_compare_extraction_detects_mismatches() -> None:
    expected = {"invoice_number": "90005", "total_amount": "999.99", "line_count": 2}
    results = compare_extraction(expected, invoice_to_fields(_invoice()))
    assert results == {"invoice_number": True, "total_amount": False, "line_count": False}


def test_aggregate_extraction() -> None:
    agg = aggregate_extraction(
        [
            {"invoice_number": True, "total_amount": True},
            {"invoice_number": True, "total_amount": False},
        ]
    )
    assert agg["invoices"] == 2
    assert agg["per_field"]["invoice_number"] == 1.0
    assert agg["per_field"]["total_amount"] == 0.5
    assert agg["overall"] == 0.75


def test_match_metrics() -> None:
    samples = [
        {"expected_status": "matched", "predicted_status": "matched", "requires_human": False},
        {"expected_status": "matched", "predicted_status": "matched", "requires_human": False},
        {
            "expected_status": "qty_variance",
            "predicted_status": "qty_variance",
            "requires_human": True,
        },
        {
            "expected_status": "matched",
            "predicted_status": "price_variance",
            "requires_human": True,
        },
    ]
    m = match_metrics(samples)
    assert m["count"] == 4
    assert m["classification_accuracy"] == 0.75  # 3/4 statuses correct
    assert m["match_rate"] == 0.5  # 2/4 predicted matched
    assert m["stp_rate"] == 0.5  # 2/4 auto-posted


def test_retrieval_metrics() -> None:
    samples = [
        {"expected_po": "PO-1", "ranked": ["PO-1", "PO-2"]},  # hit@1
        {"expected_po": "PO-3", "ranked": ["PO-2", "PO-3"]},  # rank 2 → rr 0.5
        {"expected_po": None, "ranked": ["PO-9"]},  # ignored (no expected)
    ]
    r = retrieval_metrics(samples)
    assert r["count"] == 2
    assert r["hit_at_1"] == 0.5
    assert r["mrr"] == 0.75  # (1 + 0.5) / 2


def test_report_markdown() -> None:
    report = EvaluationReport(
        dataset="data/ground_truth.json",
        invoices_evaluated=10,
        extraction={"overall": 0.95, "per_field": {"po_number": 1.0}},
        matching={"classification_accuracy": 0.9, "match_rate": 0.6, "stp_rate": 0.6},
        retrieval={"count": 8, "hit_at_1": 1.0, "mrr": 1.0},
    )
    md = report.to_markdown()
    assert "# Evaluation Report" in md
    assert "95.0%" in md
    assert "STP rate" in md
