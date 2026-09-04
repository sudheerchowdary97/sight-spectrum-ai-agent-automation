"""AR gateway protocol and the remittance-application result model."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from invoice_agent.schemas import ARItem


@runtime_checkable
class ArGateway(Protocol):
    """Read open AR items and apply cash against them."""

    def list_ar_items(self, status: str | None = None) -> list[ARItem]: ...

    def apply_cash(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class RemittanceResult(BaseModel):
    """Outcome of applying a remittance."""

    remittance_id: str
    matched: bool
    status: str  # applied | partially_applied | overpaid | unmatched
    ar_item_id: str | None = None
    application_id: str | None = None
    amount_applied: Decimal | None = None
    remaining_open: Decimal | None = None
