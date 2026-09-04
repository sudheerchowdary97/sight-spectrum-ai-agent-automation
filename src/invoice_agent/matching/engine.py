"""The matching engine: 2-way / 3-way line-level comparison (pure logic).

No I/O — takes an invoice + PO (+ optional Goods Receipt) + tolerances and
returns a :class:`MatchResult`. This is the piece validated directly against the
Task 1 labelled scenarios.
"""

from __future__ import annotations

from decimal import Decimal

from invoice_agent.schemas import (
    GoodsReceipt,
    Invoice,
    LineItem,
    MatchResult,
    MatchStatus,
    MatchType,
    PurchaseOrder,
    Variance,
)


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _by_sku_desc(lines: list) -> tuple[dict[str, object], dict[str, object]]:
    by_sku = {line.sku.strip().lower(): line for line in lines if getattr(line, "sku", None)}
    by_desc = {_norm(line.description): line for line in lines}
    return by_sku, by_desc


def _find(line: LineItem, by_sku: dict[str, object], by_desc: dict[str, object]):
    if line.sku and line.sku.strip().lower() in by_sku:
        return by_sku[line.sku.strip().lower()]
    return by_desc.get(_norm(line.description))


def _pct(actual: Decimal, expected: Decimal) -> float:
    return float((actual - expected) / expected) if expected else 0.0


def match(
    invoice: Invoice,
    purchase_order: PurchaseOrder | None,
    goods_receipt: GoodsReceipt | None,
    tolerances,
) -> MatchResult:
    """Compare an invoice against its PO (and GR) and classify the outcome."""
    if purchase_order is None:
        return MatchResult(
            invoice_number=invoice.invoice_number,
            po_number=invoice.po_number,
            match_type=MatchType.TWO_WAY,
            status=MatchStatus.MISSING_PO,
            requires_human=True,
            notes="No matching purchase order found",
        )

    match_type = MatchType.THREE_WAY if goods_receipt else MatchType.TWO_WAY
    po_by_sku, po_by_desc = _by_sku_desc(purchase_order.lines)
    gr_by_sku, gr_by_desc = _by_sku_desc(goods_receipt.lines) if goods_receipt else ({}, {})

    variances: list[Variance] = []
    matched_line_nos: set[int] = set()
    price_issue = qty_issue = False

    for inv_line in invoice.lines:
        po_line = _find(inv_line, po_by_sku, po_by_desc)
        if po_line is None:
            variances.append(
                Variance(
                    field="line",
                    line_no=inv_line.line_no,
                    expected="(no matching PO line)",
                    actual=inv_line.description,
                    within_tolerance=False,
                )
            )
            continue
        matched_line_nos.add(po_line.line_no)

        # Unit-price variance (Invoice vs PO).
        if inv_line.unit_price != po_line.unit_price:
            delta = _pct(inv_line.unit_price, po_line.unit_price)
            ok = abs(delta) <= tolerances.price_tolerance_pct
            variances.append(
                Variance(
                    field="unit_price",
                    line_no=inv_line.line_no,
                    expected=str(po_line.unit_price),
                    actual=str(inv_line.unit_price),
                    delta_pct=round(delta * 100, 2),
                    within_tolerance=ok,
                )
            )
            price_issue = price_issue or not ok

        # Quantity variance (Invoice vs PO).
        if inv_line.quantity != po_line.quantity:
            delta = _pct(inv_line.quantity, po_line.quantity)
            ok = abs(delta) <= tolerances.qty_tolerance_pct
            variances.append(
                Variance(
                    field="quantity",
                    line_no=inv_line.line_no,
                    expected=str(po_line.quantity),
                    actual=str(inv_line.quantity),
                    delta_pct=round(delta * 100, 2),
                    within_tolerance=ok,
                )
            )
            qty_issue = qty_issue or not ok

        # 3-way: invoiced quantity vs quantity actually received.
        if goods_receipt is not None:
            gr_line = _find(inv_line, gr_by_sku, gr_by_desc)
            if gr_line is not None and inv_line.quantity != gr_line.quantity_received:
                variances.append(
                    Variance(
                        field="quantity_received",
                        line_no=inv_line.line_no,
                        expected=str(gr_line.quantity_received),
                        actual=str(inv_line.quantity),
                        within_tolerance=False,
                    )
                )
                qty_issue = True

    # PO lines not present on the invoice → partial billing.
    missing = [line for line in purchase_order.lines if line.line_no not in matched_line_nos]
    for po_line in missing:
        variances.append(
            Variance(
                field="line",
                line_no=po_line.line_no,
                expected=po_line.description,
                actual="(not invoiced)",
                within_tolerance=False,
            )
        )

    # Classify (a scenario has one dominant issue; order by severity).
    if missing:
        status = MatchStatus.PARTIAL
    elif qty_issue:
        status = MatchStatus.QTY_VARIANCE
    elif price_issue:
        status = MatchStatus.PRICE_VARIANCE
    else:
        status = MatchStatus.MATCHED

    # Safety net: totals must reconcile within the absolute tolerance.
    if status is MatchStatus.MATCHED:
        total_delta = abs(invoice.total_amount - purchase_order.total_amount)
        if total_delta > tolerances.amount_tolerance_abs:
            variances.append(
                Variance(
                    field="total_amount",
                    expected=str(purchase_order.total_amount),
                    actual=str(invoice.total_amount),
                    within_tolerance=False,
                )
            )
            status = MatchStatus.PRICE_VARIANCE

    return MatchResult(
        invoice_number=invoice.invoice_number,
        po_number=purchase_order.po_number,
        gr_number=goods_receipt.gr_number if goods_receipt else None,
        match_type=match_type,
        status=status,
        variances=variances,
        requires_human=status is not MatchStatus.MATCHED,
    )
