#!/usr/bin/env python3
"""CLI: generate the synthetic invoice/PO/GR/AR dataset (Task 1).

Usage:
    python scripts/generate_synthetic_data.py --seed 42 --num-pos 60 --out data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from a source checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.synthetic.generate import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic invoice dataset.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    parser.add_argument("--num-pos", type=int, default=60, help="Number of purchase orders.")
    parser.add_argument("--out", default="data", help="Output directory (default: data).")
    args = parser.parse_args()

    summary = generate_dataset(seed=args.seed, out_dir=args.out, num_pos=args.num_pos)

    print("Synthetic dataset generated:\n")
    print(json.dumps(summary, indent=2))
    print(f"\nWritten under: {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
