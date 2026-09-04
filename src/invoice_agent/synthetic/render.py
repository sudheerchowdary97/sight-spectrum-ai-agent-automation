"""Render invoices to PDF / scanned-PDF / HTML / image.

Uses the ``[data]`` extras (fpdf2, Pillow, Jinja2). Kept isolated from
``master``/``scenarios`` so those stay dependency-light and testable.
"""

from __future__ import annotations

import io
import random
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from jinja2 import Environment, select_autoescape
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from invoice_agent.schemas import DocumentType, Invoice
from invoice_agent.synthetic.master import Vendor

_JINJA = Environment(autoescape=select_autoescape(["html"]))

# Two HTML layouts so extraction is not overfit to a single template.
_HTML_TEMPLATES = [
    """<!doctype html><html><head><meta charset="utf-8"><title>Invoice {{ inv.invoice_number }}</title>
<style>body{font-family:Arial,sans-serif;margin:40px;color:#222}
h1{color:#1a5276}table{border-collapse:collapse;width:100%;margin-top:16px}
th,td{border:1px solid #ccc;padding:8px;text-align:left}th{background:#eef}
.right{text-align:right}.meta{margin-top:8px}</style></head><body>
<h1>INVOICE</h1>
<div class="meta"><strong>Invoice #:</strong> {{ inv.invoice_number }}<br>
<strong>Date:</strong> {{ inv.invoice_date }} &nbsp; <strong>Due:</strong> {{ inv.due_date }}<br>
<strong>PO #:</strong> {{ inv.po_number or "N/A" }}</div>
<p><strong>Vendor:</strong> {{ inv.vendor_name }}<br>{{ vendor_address }}<br>{{ vendor_email }}</p>
<table><thead><tr><th>#</th><th>SKU</th><th>Description</th><th class="right">Qty</th>
<th class="right">Unit</th><th class="right">Amount</th></tr></thead><tbody>
{% for l in inv.lines %}<tr><td>{{ l.line_no }}</td><td>{{ l.sku }}</td><td>{{ l.description }}</td>
<td class="right">{{ l.quantity }}</td><td class="right">{{ "%.2f"|format(l.unit_price) }}</td>
<td class="right">{{ "%.2f"|format(l.amount) }}</td></tr>{% endfor %}</tbody></table>
<h3 class="right">Total: {{ inv.currency }} {{ "%.2f"|format(inv.total_amount) }}</h3>
</body></html>""",
    """<!doctype html><html><head><meta charset="utf-8"><title>{{ inv.vendor_name }} — {{ inv.invoice_number }}</title>
<style>body{font-family:Georgia,serif;margin:36px;color:#111}
.head{border-bottom:3px solid #900;padding-bottom:8px}
.box{float:right;text-align:right}table{width:100%;border-collapse:collapse;margin-top:20px}
td,th{padding:6px 10px;border-bottom:1px solid #ddd}tfoot td{font-weight:bold}</style></head><body>
<div class="head"><div class="box">Invoice {{ inv.invoice_number }}<br>{{ inv.invoice_date }}</div>
<h2>{{ inv.vendor_name }}</h2>{{ vendor_address }}</div>
<p>Bill against PO <strong>{{ inv.po_number or "—" }}</strong>. Payment due {{ inv.due_date }}.</p>
<table><thead><tr><th>Item</th><th>Description</th><th>Qty</th><th>Unit Price</th><th>Line Total</th></tr></thead>
<tbody>{% for l in inv.lines %}<tr><td>{{ l.sku }}</td><td>{{ l.description }}</td><td>{{ l.quantity }}</td>
<td>{{ "%.2f"|format(l.unit_price) }}</td><td>{{ "%.2f"|format(l.amount) }}</td></tr>{% endfor %}</tbody>
<tfoot><tr><td colspan="4">Total ({{ inv.currency }})</td><td>{{ "%.2f"|format(inv.total_amount) }}</td></tr></tfoot>
</table></body></html>""",
]


def _latin1(text: str) -> str:
    """Make text safe for fpdf2 core fonts (latin-1 only)."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _context(invoice: Invoice, vendor: Vendor | None) -> dict[str, object]:
    return {
        "inv": invoice,
        "vendor_address": vendor.address if vendor else "",
        "vendor_email": vendor.email if vendor else "",
    }


def render_html(invoice: Invoice, vendor: Vendor | None, variant: int = 0) -> str:
    """Render an invoice to an HTML string."""
    template = _JINJA.from_string(_HTML_TEMPLATES[variant % len(_HTML_TEMPLATES)])
    return template.render(**_context(invoice, vendor))


def render_pdf(invoice: Invoice, vendor: Vendor | None, path: Path) -> None:
    """Render a clean, digitally-generated PDF invoice."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "INVOICE", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=10)
    meta = (
        f"Invoice #: {invoice.invoice_number}    Date: {invoice.invoice_date}    "
        f"Due: {invoice.due_date}\nPO #: {invoice.po_number or 'N/A'}\n"
        f"Vendor: {invoice.vendor_name}"
    )
    if vendor:
        meta += f"\n{vendor.address}\n{vendor.email}"
    pdf.multi_cell(0, 6, _latin1(meta))
    pdf.ln(4)

    # Header row.
    widths = (12, 28, 80, 20, 25, 25)
    headers = ("#", "SKU", "Description", "Qty", "Unit", "Amount")
    pdf.set_font("Helvetica", "B", 10)
    for w, h in zip(widths, headers, strict=True):
        pdf.cell(w, 7, h, border=1)
    pdf.ln(7)

    pdf.set_font("Helvetica", size=9)
    for line in invoice.lines:
        cells = (
            str(line.line_no),
            line.sku or "",
            line.description,
            f"{line.quantity}",
            f"{line.unit_price:.2f}",
            f"{line.amount:.2f}",
        )
        for w, value in zip(widths, cells, strict=True):
            pdf.cell(w, 6, _latin1(value)[: int(w / 1.6)], border=1)
        pdf.ln(6)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        0, 8, f"Total: {invoice.currency} {invoice.total_amount:.2f}", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.output(str(path))


def _render_image(invoice: Invoice, vendor: Vendor | None) -> Image.Image:
    """Draw the invoice onto a white canvas (a 'clean scan')."""
    width, height = 1000, 1400
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title = ImageFont.load_default(size=44)
    label = ImageFont.load_default(size=24)
    body = ImageFont.load_default(size=20)

    y = 40
    draw.text((40, y), "INVOICE", font=title, fill="black")
    y += 70
    for text in (
        f"Invoice #: {invoice.invoice_number}    Date: {invoice.invoice_date}",
        f"PO #: {invoice.po_number or 'N/A'}    Due: {invoice.due_date}",
        f"Vendor: {invoice.vendor_name}",
        (vendor.address if vendor else ""),
    ):
        if text:
            draw.text((40, y), text, font=label, fill="black")
            y += 34
    y += 20

    header = f"{'#':<4}{'SKU':<12}{'Description':<34}{'Qty':>6}{'Unit':>10}{'Amount':>12}"
    draw.text((40, y), header, font=body, fill="black")
    y += 30
    draw.line((40, y, width - 40, y), fill="black", width=1)
    y += 10
    for line in invoice.lines:
        row = (
            f"{line.line_no:<4}{(line.sku or ''):<12}{line.description[:32]:<34}"
            f"{line.quantity!s:>6}{line.unit_price:>10.2f}{line.amount:>12.2f}"
        )
        draw.text((40, y), row, font=body, fill="black")
        y += 28
    y += 20
    draw.text(
        (40, y), f"TOTAL: {invoice.currency} {invoice.total_amount:.2f}", font=label, fill="black"
    )
    return img


def _degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    """Apply scan-like artefacts: slight rotation, blur, JPEG compression."""
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=False, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=68)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def _image_to_pdf(img: Image.Image, path: Path) -> None:
    pdf = FPDF(unit="pt", format=(img.width, img.height))
    pdf.add_page()
    pdf.image(img, x=0, y=0, w=img.width, h=img.height)
    pdf.output(str(path))


def render_document(
    invoice: Invoice,
    vendor: Vendor | None,
    document_type: DocumentType,
    out_dir: Path,
    rng: random.Random,
) -> list[Path]:
    """Render ``invoice`` in the requested format; return the file(s) written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = invoice.invoice_id

    if document_type is DocumentType.HTML:
        path = out_dir / f"{stem}.html"
        variant = int(Decimal(invoice.total_amount)) % len(_HTML_TEMPLATES)
        path.write_text(render_html(invoice, vendor, variant), encoding="utf-8")
        return [path]

    if document_type is DocumentType.PDF:
        path = out_dir / f"{stem}.pdf"
        render_pdf(invoice, vendor, path)
        return [path]

    if document_type is DocumentType.IMAGE:
        path = out_dir / f"{stem}.png"
        _degrade(_render_image(invoice, vendor), rng).save(path)
        return [path]

    # SCANNED_PDF: degraded image embedded in a PDF.
    path = out_dir / f"{stem}.pdf"
    _image_to_pdf(_degrade(_render_image(invoice, vendor), rng), path)
    return [path]
