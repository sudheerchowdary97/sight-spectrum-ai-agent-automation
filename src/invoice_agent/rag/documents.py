"""Text representations for indexing POs and querying with invoices.

Both a PO document and an invoice query are rendered the same way (vendor + line
items + total) so their embeddings live in the same semantic space.
"""

from __future__ import annotations

from invoice_agent.schemas import Invoice, PurchaseOrder


def _items_text(lines: list) -> str:
    return "; ".join(f"{line.quantity} x {line.description} @ {line.unit_price}" for line in lines)


def po_to_text(po: PurchaseOrder) -> str:
    """Render a PO as the text that gets embedded and indexed."""
    return (
        f"Vendor: {po.vendor_name}\n"
        f"Total: {po.currency} {po.total_amount}\n"
        f"Items: {_items_text(po.lines)}"
    )


def po_metadata(po: PurchaseOrder) -> dict[str, str]:
    """Metadata stored alongside the PO vector, returned on retrieval."""
    return {
        "po_number": po.po_number,
        "vendor_id": po.vendor_id,
        "vendor_name": po.vendor_name,
        "total_amount": str(po.total_amount),
    }


def invoice_to_query(invoice: Invoice) -> str:
    """Render an invoice as the retrieval query (same shape as a PO document)."""
    return (
        f"Vendor: {invoice.vendor_name}\n"
        f"Total: {invoice.currency} {invoice.total_amount}\n"
        f"Items: {_items_text(invoice.lines)}"
    )
