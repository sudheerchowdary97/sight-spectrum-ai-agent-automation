#!/usr/bin/env python3
"""CLI: apply AR remittances against open AR items (Task 10).

Reads the generated remittances (data/master/remittances.json), matches each to
an open AR item, and applies cash via the ERP. Requires the stack up.

Usage:
    python scripts/run_ar.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_agent.ar.service import build_remittance_service
from invoice_agent.config import get_settings
from invoice_agent.schemas import Remittance

_FIELDS = {"remittance_id", "customer_name", "amount", "currency", "references", "remittance_date"}


def _load_remittances(master_dir: Path) -> list[Remittance]:
    data = json.loads((master_dir / "remittances.json").read_text())
    return [
        Remittance.model_validate({k: v for k, v in row.items() if k in _FIELDS}) for row in data
    ]


def main() -> None:
    settings = get_settings()
    remittances = _load_remittances(Path(settings.erp_data_dir))
    service = build_remittance_service(settings)

    print(f"Applying {len(remittances)} remittance(s)...\n")
    print(f"{'remittance':<12} {'ar_item':<10} {'status':<18} {'applied':<10} remaining")
    print("-" * 62)
    for remittance in remittances:
        result = service.apply(remittance)
        print(
            f"{result.remittance_id:<12} {(result.ar_item_id or '-'):<10} "
            f"{result.status:<18} {result.amount_applied or '-'!s:<10} "
            f"{result.remaining_open if result.remaining_open is not None else '-'}"
        )


if __name__ == "__main__":
    main()
