"""Tests for the synthetic dataset generator (Task 1).

Master/scenario logic is validated unconditionally. The full render+email
pipeline is exercised only when the ``[data]`` extras (fpdf2, Pillow, Jinja2)
are installed; otherwise that test is skipped.
"""

from __future__ import annotations

import json
import random
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_agent.schemas import DocumentType
from invoice_agent.synthetic.master import build_master, money
from invoice_agent.synthetic.scenarios import Scenario, derive_from_po


def test_master_is_deterministic() -> None:
    a = build_master(seed=7, num_pos=15)
    b = build_master(seed=7, num_pos=15)
    assert [po.po_number for po in a.purchase_orders] == [po.po_number for po in b.purchase_orders]
    assert a.purchase_orders[0].total_amount == b.purchase_orders[0].total_amount


def test_po_totals_match_line_sums() -> None:
    master = build_master(seed=1, num_pos=20)
    for po in master.purchase_orders:
        assert po.total_amount == money(sum((line.amount for line in po.lines), Decimal(0)))


def test_goods_receipts_reference_real_pos() -> None:
    master = build_master(seed=3, num_pos=25)
    po_numbers = {po.po_number for po in master.purchase_orders}
    assert master.goods_receipts, "expected some goods receipts"
    assert all(gr.po_number in po_numbers for gr in master.goods_receipts)


def test_price_variance_changes_total() -> None:
    master = build_master(seed=5, num_pos=10)
    po = master.purchase_orders[0]
    vendor = master.vendor_by_id[po.vendor_id]

    invoice, _printed, gt = derive_from_po(
        seq=1,
        invoice_number="90001",
        po=po,
        vendor=vendor,
        scenario=Scenario.PRICE_VARIANCE,
        document_type=DocumentType.PDF,
        gr_present=True,
        fuzz_vendor=False,
        rng=random.Random(0),
    )
    assert invoice.total_amount != po.total_amount
    assert gt.expected_requires_human is True
    assert gt.expected_status is not None
    assert gt.expected_status.value == "price_variance"


def test_full_generation_end_to_end(tmp_path: Path) -> None:
    pytest.importorskip("fpdf")
    pytest.importorskip("PIL")
    pytest.importorskip("jinja2")
    from invoice_agent.synthetic.generate import generate_dataset

    summary = generate_dataset(seed=42, out_dir=tmp_path, num_pos=12)

    gt = json.loads((tmp_path / "ground_truth.json").read_text())
    assert len(gt) == summary["counts"]["invoices"]
    for record in gt:
        assert (tmp_path / "inbox" / f"{record['email_id']}.eml").exists()
        for fname in record["source_files"]:
            assert (tmp_path / "generated" / "invoices" / fname).exists()

    scenarios = {record["scenario"] for record in gt}
    assert {"clean", "missing_po", "duplicate"} <= scenarios
    assert 0.0 < summary["expected_stp_rate"] <= 1.0
