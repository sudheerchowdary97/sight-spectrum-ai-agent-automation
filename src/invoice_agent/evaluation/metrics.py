"""Pure metric functions for evaluation.

* Extraction accuracy — field-level correctness of extracted invoices.
* Match metrics — classification accuracy vs ground truth, match rate, STP rate.
* Retrieval metrics — hit@1 and MRR of RAG candidate POs.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from invoice_agent.schemas import Invoice

# Fields scored for extraction accuracy, with type-aware comparison.
EXTRACTION_FIELDS = ["invoice_number", "vendor_name", "total_amount", "po_number", "line_count"]
_NUMERIC_FIELDS = {"total_amount"}
_INT_FIELDS = {"line_count"}


def _norm_str(value: Any) -> str:
    return " ".join(str(value).split()).lower()


def _field_equal(field: str, expected: Any, predicted: Any) -> bool:
    if field in _NUMERIC_FIELDS:
        try:
            cents = Decimal("0.01")
            return Decimal(str(expected)).quantize(cents) == Decimal(str(predicted)).quantize(cents)
        except (InvalidOperation, ValueError):
            return False
    if field in _INT_FIELDS:
        try:
            return int(expected) == int(predicted)
        except (ValueError, TypeError):
            return False
    return _norm_str(expected) == _norm_str(predicted)


def invoice_to_fields(invoice: Invoice) -> dict[str, Any]:
    """Project an extracted invoice into the scored field set."""
    return {
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "total_amount": f"{invoice.total_amount:.2f}",
        "po_number": invoice.po_number or "",
        "line_count": len(invoice.lines),
    }


def compare_extraction(
    expected_fields: dict[str, Any], predicted_fields: dict[str, Any]
) -> dict[str, bool]:
    """Compare predicted vs expected fields; returns per-field correctness."""
    results: dict[str, bool] = {}
    for field in EXTRACTION_FIELDS:
        if field in expected_fields:
            results[field] = _field_equal(
                field, expected_fields[field], predicted_fields.get(field, "")
            )
    return results


def aggregate_extraction(per_invoice: list[dict[str, bool]]) -> dict[str, Any]:
    """Aggregate per-invoice field results into per-field and overall accuracy."""
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for result in per_invoice:
        for field, ok in result.items():
            totals[field][0] += int(ok)
            totals[field][1] += 1
    per_field = {f: round(c / n, 4) if n else 0.0 for f, (c, n) in totals.items()}
    flags = [ok for result in per_invoice for ok in result.values()]
    overall = round(sum(flags) / len(flags), 4) if flags else 0.0
    return {"invoices": len(per_invoice), "overall": overall, "per_field": per_field}


def match_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Classification accuracy (vs ground truth), match rate, STP rate.

    Each sample: ``{expected_status, predicted_status, requires_human}``.
    """
    n = len(samples)
    if n == 0:
        return {"count": 0, "classification_accuracy": 0.0, "match_rate": 0.0, "stp_rate": 0.0}
    correct = sum(1 for s in samples if s["predicted_status"] == s["expected_status"])
    matched = sum(1 for s in samples if s["predicted_status"] == "matched")
    stp = sum(1 for s in samples if s["predicted_status"] == "matched" and not s["requires_human"])
    return {
        "count": n,
        "classification_accuracy": round(correct / n, 4),
        "match_rate": round(matched / n, 4),
        "stp_rate": round(stp / n, 4),
    }


def retrieval_metrics(samples: list[dict[str, Any]], k: int = 5) -> dict[str, Any]:
    """Hit@1 and MRR over samples that have a known expected PO.

    Each sample: ``{expected_po: str | None, ranked: list[str]}``.
    """
    considered = [s for s in samples if s.get("expected_po")]
    if not considered:
        return {"count": 0, "hit_at_1": 0.0, "mrr": 0.0}
    hits_at_1 = 0
    reciprocal_rank = 0.0
    for sample in considered:
        ranked = sample["ranked"][:k]
        if ranked and ranked[0] == sample["expected_po"]:
            hits_at_1 += 1
        for rank, po in enumerate(ranked, start=1):
            if po == sample["expected_po"]:
                reciprocal_rank += 1 / rank
                break
    m = len(considered)
    return {"count": m, "hit_at_1": round(hits_at_1 / m, 4), "mrr": round(reciprocal_rank / m, 4)}
