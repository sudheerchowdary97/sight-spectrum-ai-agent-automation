#!/usr/bin/env python3
"""CLI: index master POs into PGVector and test semantic retrieval (Task 5).

Runs the REAL LlamaIndex + PGVector + Ollama-embeddings path, so it needs the
stack up and the embedding model pulled. It indexes all master POs, then for a
sample of them builds a query with a *fuzzed* vendor name and checks that the
correct PO is retrieved — demonstrating robustness to vendor-name variation.

Usage:
    python scripts/rag_index_retrieve.py [--top-k 5] [--sample 10]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.config import get_settings
from invoice_agent.rag.service import build_rag_service
from invoice_agent.schemas import PurchaseOrder
from invoice_agent.synthetic.scenarios import fuzz_vendor_name


def _load_pos(master_dir: Path) -> list[PurchaseOrder]:
    data = json.loads((master_dir / "purchase_orders.json").read_text())
    return [PurchaseOrder.model_validate(d) for d in data]


def _query_with_fuzzed_vendor(po: PurchaseOrder, rng: random.Random) -> str:
    items = "; ".join(
        f"{line.quantity} x {line.description} @ {line.unit_price}" for line in po.lines
    )
    vendor = fuzz_vendor_name(po.vendor_name, rng)
    return f"Vendor: {vendor}\nTotal: {po.currency} {po.total_amount}\nItems: {items}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Index POs and test retrieval.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--master-dir", default="data/master")
    args = parser.parse_args()

    settings = get_settings()
    pos = _load_pos(Path(args.master_dir))
    print(f"Loaded {len(pos)} purchase orders. Indexing into PGVector...")

    rag = build_rag_service(settings)
    rag.index_master(pos)
    print("Indexed. Testing retrieval with fuzzed vendor names:\n")

    rng = random.Random(0)
    sample = pos[: args.sample]
    hits = 0
    for po in sample:
        candidates = rag._index.retrieve(_query_with_fuzzed_vendor(po, rng), top_k=args.top_k)
        top = candidates[0].po_number if candidates else "-"
        rank = next((i + 1 for i, c in enumerate(candidates) if c.po_number == po.po_number), None)
        hit = rank == 1
        hits += int(hit)
        status = "HIT" if hit else "miss"
        print(f"  {po.po_number} (vendor '{po.vendor_name}') -> top={top} rank={rank} {status}")

    print(f"\nhit@1: {hits}/{len(sample)} = {hits / len(sample):.0%}")


if __name__ == "__main__":
    main()
