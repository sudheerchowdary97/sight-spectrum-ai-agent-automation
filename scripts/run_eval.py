#!/usr/bin/env python3
"""CLI: evaluate the pipeline against ground truth and write a report (Task 13).

Runs the real pipeline (Docling + Ollama + PGVector + ERP) over the labelled
dataset and writes data/evaluation_report.{json,md}.

Usage:
    python scripts/run_eval.py --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.config import get_settings
from invoice_agent.evaluation.harness import run_evaluation
from invoice_agent.observability import configure_tracing


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the pipeline vs ground truth.")
    parser.add_argument("--limit", type=int, default=None, help="Max invoices to evaluate")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    settings = get_settings()
    configure_tracing(settings)
    report = run_evaluation(settings, limit=args.limit, data_dir=args.data_dir)

    out = Path(args.data_dir)
    (out / "evaluation_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / "evaluation_report.md").write_text(report.to_markdown(), encoding="utf-8")

    print(report.to_markdown())
    print(f"\nWritten: {out / 'evaluation_report.json'} and .md")


if __name__ == "__main__":
    main()
