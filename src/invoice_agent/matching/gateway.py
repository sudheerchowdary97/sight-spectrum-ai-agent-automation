"""ERP gateway protocol used by matching (and later posting).

Both the real HTTP :class:`~invoice_agent.erp_client.ErpClient` and in-memory
test doubles satisfy this, so matching logic is decoupled from transport.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_agent.schemas import GoodsReceipt, PurchaseOrder


@runtime_checkable
class PoGateway(Protocol):
    """Read-only access to Purchase Orders and their Goods Receipts."""

    def get_purchase_order(self, po_number: str) -> PurchaseOrder | None: ...

    def get_goods_receipts(self, po_number: str) -> list[GoodsReceipt]: ...
