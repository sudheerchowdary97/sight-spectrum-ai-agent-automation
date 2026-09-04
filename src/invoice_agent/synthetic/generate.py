"""Dataset orchestrator: build master data, invoices, documents, emails, labels.

Entry point: :func:`generate_dataset`. Deterministic for a given seed. Writes:

    <out>/master/           vendors, customers, purchase_orders, goods_receipts,
                            ar_items, remittances  (JSON)
    <out>/generated/invoices/   rendered PDF / scanned-PDF / HTML / image files
    <out>/inbox/            .eml fixtures (invoices + remittances)
    <out>/ground_truth.json labelled expectations for every invoice
    <out>/summary.json      dataset statistics
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from invoice_agent.schemas import ARItem, DocumentType, Invoice, MatchStatus, Remittance
from invoice_agent.synthetic import email_fixtures, render
from invoice_agent.synthetic.master import MasterData, Vendor, build_master, money
from invoice_agent.synthetic.scenarios import (
    GroundTruthRecord,
    Scenario,
    build_missing_po,
    derive_from_po,
)

# Document-type weights (must sum to 1.0).
_DOC_WEIGHTS: list[tuple[DocumentType, float]] = [
    (DocumentType.PDF, 0.40),
    (DocumentType.SCANNED_PDF, 0.30),
    (DocumentType.HTML, 0.20),
    (DocumentType.IMAGE, 0.10),
]

_FUZZ_VENDOR_PROB = 0.30


def _pick_doc_type(rng: random.Random) -> DocumentType:
    roll = rng.random()
    cumulative = 0.0
    for doc_type, weight in _DOC_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return doc_type
    return _DOC_WEIGHTS[-1][0]


def _plan_scenarios(n: int, rng: random.Random) -> list[Scenario]:
    """Assign a scenario to each of the ``n`` purchase orders."""
    counts = {
        Scenario.PRICE_VARIANCE: round(0.12 * n),
        Scenario.QTY_VARIANCE: round(0.10 * n),
        Scenario.PARTIAL: round(0.08 * n),
    }
    plan: list[Scenario] = []
    for scenario, count in counts.items():
        plan.extend([scenario] * count)
    plan.extend([Scenario.CLEAN] * (n - len(plan)))
    rng.shuffle(plan)
    return plan


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _dump_master(master: MasterData, master_dir: Path) -> None:
    _write_json(master_dir / "vendors.json", [asdict(v) for v in master.vendors])
    _write_json(master_dir / "customers.json", [asdict(c) for c in master.customers])
    _write_json(
        master_dir / "purchase_orders.json",
        [po.model_dump(mode="json") for po in master.purchase_orders],
    )
    _write_json(
        master_dir / "goods_receipts.json",
        [gr.model_dump(mode="json") for gr in master.goods_receipts],
    )
    _write_json(
        master_dir / "ar_items.json", [ar.model_dump(mode="json") for ar in master.ar_items]
    )


def _emit_invoice_email(
    invoice: Invoice,
    vendor: Vendor | None,
    files: list[Path],
    inbox_dir: Path,
) -> str:
    """Write the ingestion email for an invoice; return its email id."""
    email_id = f"email-{invoice.invoice_id}"
    email_fixtures.build_email(
        email_id=email_id,
        sender_name=invoice.vendor_name,
        sender_email=(vendor.email if vendor else "unknown@vendor.example"),
        subject=f"Invoice {invoice.invoice_number} from {invoice.vendor_name}",
        body=(
            f"Dear Accounts Payable,\n\nPlease find attached invoice "
            f"{invoice.invoice_number} for PO {invoice.po_number or 'N/A'}, "
            f"total {invoice.currency} {invoice.total_amount:.2f}.\n\nRegards,\n"
            f"{invoice.vendor_name}"
        ),
        attachments=files,
        out_dir=inbox_dir,
    )
    return email_id


def _remittance_html(remittance: Remittance, ar: ARItem) -> str:
    return (
        f"<html><body><h2>Remittance Advice</h2>"
        f"<p>From: {remittance.customer_name}</p>"
        f"<p>Payment of <strong>{remittance.currency} {remittance.amount:.2f}</strong> "
        f"applied to invoice <strong>{ar.invoice_number}</strong>.</p>"
        f"<p>Date: {remittance.remittance_date}</p></body></html>"
    )


def _generate_remittances(
    master: MasterData,
    rng: random.Random,
    gen_dir: Path,
    inbox_dir: Path,
    master_dir: Path,
) -> int:
    """Generate remittance advice emails for a subset of open AR items."""
    sample = rng.sample(master.ar_items, min(10, len(master.ar_items)))
    records: list[dict[str, object]] = []
    for i, ar in enumerate(sample):
        full = rng.random() < 0.7
        amount = ar.open_amount if full else money(ar.open_amount * Decimal("0.6"))
        remittance = Remittance(
            remittance_id=f"REM-{8001 + i}",
            customer_name=ar.customer_name,
            amount=amount,
            references=[ar.invoice_number],
            remittance_date=ar.due_date or master.purchase_orders[0].order_date,
        )
        html_path = gen_dir / f"{remittance.remittance_id}.html"
        html_path.write_text(_remittance_html(remittance, ar), encoding="utf-8")
        email_id = f"email-{remittance.remittance_id}"
        email_fixtures.build_email(
            email_id=email_id,
            sender_name=ar.customer_name,
            sender_email=f"remittance@{ar.customer_id.lower()}.example",
            subject=f"Remittance advice — invoice {ar.invoice_number}",
            body=f"Payment of {remittance.currency} {amount:.2f} for {ar.invoice_number}.",
            attachments=[html_path],
            out_dir=inbox_dir,
        )
        records.append(
            {
                **remittance.model_dump(mode="json"),
                "email_id": email_id,
                "expected_ar_item_id": ar.ar_item_id,
                "expected_apply": "full" if full else "partial",
            }
        )
    _write_json(master_dir / "remittances.json", records)
    return len(records)


def generate_dataset(
    *,
    seed: int = 42,
    out_dir: str | Path = "data",
    num_pos: int = 60,
    num_missing_po: int | None = None,
    num_duplicates: int | None = None,
) -> dict[str, object]:
    """Generate the full synthetic dataset. Returns a summary dict."""
    rng = random.Random(seed)
    base = Path(out_dir)
    master_dir = base / "master"
    gen_dir = base / "generated" / "invoices"
    inbox_dir = base / "inbox"

    master = build_master(seed, num_pos=num_pos)
    _dump_master(master, master_dir)

    num_missing_po = round(0.10 * num_pos) if num_missing_po is None else num_missing_po
    num_duplicates = round(0.08 * num_pos) if num_duplicates is None else num_duplicates

    ground_truth: list[GroundTruthRecord] = []
    clean_invoices: list[tuple[Invoice, Vendor | None, list[Path], DocumentType]] = []
    seq = 1

    # --- Invoices derived from POs ---
    plan = _plan_scenarios(len(master.purchase_orders), rng)
    for po, scenario in zip(master.purchase_orders, plan, strict=True):
        vendor = master.vendor_by_id.get(po.vendor_id)
        doc_type = _pick_doc_type(rng)
        fuzz = scenario in {Scenario.CLEAN, Scenario.PRICE_VARIANCE, Scenario.QTY_VARIANCE} and (
            rng.random() < _FUZZ_VENDOR_PROB
        )
        invoice, _printed, gt = derive_from_po(
            seq=seq,
            invoice_number=str(90000 + seq),
            po=po,
            vendor=vendor,  # type: ignore[arg-type]
            scenario=scenario,
            document_type=doc_type,
            gr_present=po.po_number in master.gr_by_po,
            fuzz_vendor=fuzz,
            rng=rng,
        )
        files = render.render_document(invoice, vendor, doc_type, gen_dir, rng)
        gt.email_id = _emit_invoice_email(invoice, vendor, files, inbox_dir)
        gt.source_files = [f.name for f in files]
        ground_truth.append(gt)
        if scenario is Scenario.CLEAN:
            clean_invoices.append((invoice, vendor, files, doc_type))
        seq += 1

    # --- Missing-PO invoices (no backing PO in the ERP) ---
    for _ in range(num_missing_po):
        vendor = rng.choice(master.vendors)
        doc_type = _pick_doc_type(rng)
        invoice, _printed, gt = build_missing_po(
            seq=seq,
            invoice_number=str(90000 + seq),
            vendor=vendor,
            document_type=doc_type,
            rng=rng,
        )
        files = render.render_document(invoice, vendor, doc_type, gen_dir, rng)
        gt.email_id = _emit_invoice_email(invoice, vendor, files, inbox_dir)
        gt.source_files = [f.name for f in files]
        ground_truth.append(gt)
        seq += 1

    # --- Duplicate invoices (re-sent copies of clean ones) ---
    if clean_invoices:
        for i in range(num_duplicates):
            invoice, vendor, files, doc_type = rng.choice(clean_invoices)
            email_id = f"email-dup-{i}-{invoice.invoice_id}"
            email_fixtures.build_email(
                email_id=email_id,
                sender_name=invoice.vendor_name,
                sender_email=(vendor.email if vendor else "unknown@vendor.example"),
                subject=f"Reminder: Invoice {invoice.invoice_number} from {invoice.vendor_name}",
                body=f"Following up on invoice {invoice.invoice_number} (resent copy).",
                attachments=files,
                out_dir=inbox_dir,
            )
            ground_truth.append(
                GroundTruthRecord(
                    invoice_number=invoice.invoice_number,
                    scenario=Scenario.DUPLICATE,
                    expected_status=MatchStatus.DUPLICATE,
                    expected_match_type=next(
                        gt.expected_match_type
                        for gt in ground_truth
                        if gt.invoice_number == invoice.invoice_number
                    ),
                    expected_requires_human=True,
                    po_number=invoice.po_number,
                    linked_po_exists=True,
                    duplicate_of=invoice.invoice_number,
                    document_type=doc_type,
                    email_id=email_id,
                    source_files=[f.name for f in files],
                    expected_fields={
                        "invoice_number": invoice.invoice_number,
                        "vendor_name": invoice.vendor_name,
                        "invoice_date": invoice.invoice_date.isoformat(),
                        "currency": invoice.currency,
                        "total_amount": f"{invoice.total_amount:.2f}",
                        "po_number": invoice.po_number or "",
                        "line_count": len(invoice.lines),
                    },
                )
            )

    # --- AR remittances (mirror track) ---
    num_remittances = _generate_remittances(master, rng, gen_dir, inbox_dir, master_dir)

    _write_json(base / "ground_truth.json", [gt.model_dump(mode="json") for gt in ground_truth])

    summary = {
        "seed": seed,
        "counts": {
            "vendors": len(master.vendors),
            "customers": len(master.customers),
            "purchase_orders": len(master.purchase_orders),
            "goods_receipts": len(master.goods_receipts),
            "ar_items": len(master.ar_items),
            "invoices": len(ground_truth),
            "remittances": num_remittances,
        },
        "by_scenario": dict(Counter(gt.scenario.value for gt in ground_truth)),
        "by_document_type": dict(Counter(gt.document_type.value for gt in ground_truth)),
        "expected_stp_rate": round(
            sum(1 for gt in ground_truth if not gt.expected_requires_human) / len(ground_truth),
            3,
        ),
    }
    _write_json(base / "summary.json", summary)
    return summary
