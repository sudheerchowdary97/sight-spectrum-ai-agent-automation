"""Evaluation harness: run the real pipeline over the dataset and score it.

Runs in Docker (needs Docling + Ollama + PGVector + ERP). Compares pipeline
output to the auto-labelled ``ground_truth.json`` and produces an
:class:`EvaluationReport`.
"""

from __future__ import annotations

import json
from pathlib import Path

from invoice_agent.config import Settings
from invoice_agent.evaluation.metrics import (
    aggregate_extraction,
    compare_extraction,
    invoice_to_fields,
    match_metrics,
    retrieval_metrics,
)
from invoice_agent.evaluation.report import EvaluationReport
from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import PurchaseOrder

log = get_logger("evaluation")


def run_evaluation(
    settings: Settings,
    *,
    limit: int | None = None,
    data_dir: str | Path = "data",
    ragas: bool = False,
) -> EvaluationReport:
    """Run the pipeline over the labelled dataset and compute metrics."""
    from invoice_agent.extraction.service import build_extraction_service
    from invoice_agent.ingestion.providers.folder import FolderProvider
    from invoice_agent.ingestion.service import IngestionService
    from invoice_agent.matching.service import build_match_service
    from invoice_agent.rag.documents import invoice_to_query, po_to_text
    from invoice_agent.rag.service import build_rag_service

    base = Path(data_dir)
    ground_truth = json.loads((base / "ground_truth.json").read_text())
    if limit is not None:
        ground_truth = ground_truth[:limit]

    # Index POs so retrieval works.
    pos = [
        PurchaseOrder.model_validate(d)
        for d in json.loads((base / "master" / "purchase_orders.json").read_text())
    ]
    po_text = {po.po_number: po_to_text(po) for po in pos}
    rag = build_rag_service(settings)
    rag.index_master(pos)

    extractor = build_extraction_service(settings)
    matcher = build_match_service(settings)
    ingestion = IngestionService(FolderProvider(settings.email_replay_dir), settings.ingested_dir)

    invoices_dir = base / "generated" / "invoices"
    extraction_results: list[dict] = []
    match_samples: list[dict] = []
    retrieval_samples: list[dict] = []
    ragas_samples: list[dict] = []

    for record in ground_truth:
        source_files = record.get("source_files") or []
        if not source_files:
            continue
        path = invoices_dir / source_files[0]
        if not path.exists():
            continue

        documents = ingestion.ingest_raw(
            filename=path.name, content_type=None, content=path.read_bytes()
        )
        if not documents:
            continue
        invoice = extractor.extract(documents[0]).invoice

        extraction_results.append(
            compare_extraction(record.get("expected_fields", {}), invoice_to_fields(invoice))
        )
        match = matcher.match_invoice(invoice)
        match_samples.append(
            {
                "expected_status": record["expected_status"],
                "predicted_status": match.status.value,
                "requires_human": match.requires_human,
            }
        )
        candidates = rag.find_candidate_pos(invoice, top_k=5)
        expected_po = record["po_number"] if record.get("linked_po_exists") else None
        retrieval_samples.append(
            {"expected_po": expected_po, "ranked": [c.po_number for c in candidates]}
        )
        if expected_po and expected_po in po_text:
            ragas_samples.append(
                {
                    "query": invoice_to_query(invoice),
                    "contexts": [
                        po_text[c.po_number] for c in candidates if c.po_number in po_text
                    ],
                    "reference": po_text[expected_po],
                }
            )
        log.info("eval.invoice", invoice_number=invoice.invoice_number, status=match.status.value)

    report = EvaluationReport(
        dataset=str(base / "ground_truth.json"),
        invoices_evaluated=len(extraction_results),
        extraction=aggregate_extraction(extraction_results),
        matching=match_metrics(match_samples),
        retrieval=retrieval_metrics(retrieval_samples),
    )
    if ragas:
        from invoice_agent.evaluation.ragas_eval import evaluate_with_ragas

        report.ragas = evaluate_with_ragas(ragas_samples, settings)
    return report
