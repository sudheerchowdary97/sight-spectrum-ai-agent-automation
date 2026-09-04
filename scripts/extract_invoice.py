#!/usr/bin/env python3
"""CLI: run the real ingestion + Docling + Ollama extraction on a file (Task 4).

This exercises the FULL extraction path (Docling parsing + Ollama LLM), so it
requires the ``[agent]`` extras (Python ≤3.12) and a running Ollama with the
configured model pulled.

Usage:
    python scripts/extract_invoice.py data/generated/invoices/INV-00002.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.config import get_settings
from invoice_agent.extraction.service import build_extraction_service
from invoice_agent.ingestion.providers.folder import FolderProvider
from invoice_agent.ingestion.service import IngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest + extract a single invoice file.")
    parser.add_argument("path", help="Path to an invoice document (pdf/png/html) or .eml")
    args = parser.parse_args()

    settings = get_settings()
    path = Path(args.path)
    content = path.read_bytes()

    # 1) Ingest the file (classify + persist).
    ingestion = IngestionService(FolderProvider(settings.email_replay_dir), settings.ingested_dir)
    documents = ingestion.ingest_raw(filename=path.name, content_type=None, content=content)
    if not documents:
        print(f"No invoice document recognised in {path}", file=sys.stderr)
        raise SystemExit(1)

    # 2) Extract fields via Docling + Ollama.
    extractor = build_extraction_service(settings)
    for document in documents:
        result = extractor.extract(document)
        print(
            f"\n=== {document.attachment_filename} "
            f"(confidence={result.confidence}, warnings={result.warnings}) ==="
        )
        print(result.invoice.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
