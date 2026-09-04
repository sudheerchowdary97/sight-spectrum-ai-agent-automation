"""Evaluation report model + markdown rendering."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvaluationReport(BaseModel):
    """Aggregated evaluation results."""

    dataset: str
    invoices_evaluated: int
    extraction: dict[str, Any] = Field(default_factory=dict)
    matching: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        ext = self.extraction
        mat = self.matching
        ret = self.retrieval
        lines = [
            "# Evaluation Report",
            "",
            f"- Dataset: `{self.dataset}`",
            f"- Invoices evaluated: **{self.invoices_evaluated}**",
            "",
            "## Extraction accuracy",
            f"- Overall field accuracy: **{_pct(ext.get('overall'))}**",
        ]
        for field, score in sorted(ext.get("per_field", {}).items()):
            lines.append(f"  - {field}: {_pct(score)}")
        accuracy = _pct(mat.get("classification_accuracy"))
        lines += [
            "",
            "## Matching",
            f"- Classification accuracy vs ground truth: **{accuracy}**",
            f"- Match rate: **{_pct(mat.get('match_rate'))}**",
            f"- STP rate (auto-posted): **{_pct(mat.get('stp_rate'))}**",
            "",
            "## Retrieval (RAG candidate PO)",
            f"- Evaluated: {ret.get('count', 0)}",
            f"- hit@1: **{_pct(ret.get('hit_at_1'))}**",
            f"- MRR: **{ret.get('mrr', 0.0)}**",
        ]
        return "\n".join(lines)


def _pct(value: float | None) -> str:
    return f"{(value or 0.0) * 100:.1f}%"
