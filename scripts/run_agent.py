#!/usr/bin/env python3
"""CLI: run the full agentic pipeline over inbox invoices (Task 7).

Ingests invoice emails (folder replay), then runs each through the LangGraph
agent (extract → match → post/escalate → audit). Requires the stack up
(Docling + Ollama + ERP). Remittances are handled by the AR track (Task 10).

Usage:
    python scripts/run_agent.py --limit 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.config import get_settings
from invoice_agent.ingestion.providers import build_provider
from invoice_agent.ingestion.service import IngestionService
from invoice_agent.observability import configure_tracing
from invoice_agent.orchestration.graph import build_agent_runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent over inbox invoices.")
    parser.add_argument("--limit", type=int, default=5, help="Max emails to process")
    args = parser.parse_args()

    settings = get_settings()
    configure_tracing(settings)
    ingestion = IngestionService(build_provider(settings), settings.ingested_dir)
    runner = build_agent_runner(settings)

    documents = ingestion.ingest_from_provider(limit=args.limit)
    invoice_docs = [d for d in documents if not d.attachment_filename.startswith("REM-")]
    print(f"Processing {len(invoice_docs)} invoice document(s) through the agent...\n")

    print(f"{'invoice':<10} {'status':<15} {'decision':<10} {'journal':<12} audit")
    print("-" * 70)
    for doc in invoice_docs:
        state = runner.run(doc)
        invoice = state.get("invoice")
        match = state.get("match")
        journal = state.get("journal")
        trail = " → ".join(rec.decision.value for rec in state.get("audit", []))
        print(
            f"{(invoice.invoice_number if invoice else '?'):<10} "
            f"{(match.status.value if match else '?'):<15} "
            f"{state.get('decision', '?'):<10} "
            f"{(journal.journal_id if journal else '-'):<12} {trail}"
        )


if __name__ == "__main__":
    main()
