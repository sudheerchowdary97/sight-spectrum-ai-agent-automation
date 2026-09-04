"""Configurable matching tolerances (with optional per-vendor overrides)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from invoice_agent.config import Settings


class Tolerances(BaseModel):
    """Thresholds within which a variance is auto-accepted."""

    price_tolerance_pct: float  # e.g. 0.02 = ±2% unit-price
    qty_tolerance_pct: float  # e.g. 0.0 = quantities must match exactly
    amount_tolerance_abs: Decimal  # absolute total rounding allowance


class ToleranceProvider:
    """Supplies tolerances, defaulting globally with optional per-vendor overrides."""

    def __init__(
        self, default: Tolerances, per_vendor: dict[str, Tolerances] | None = None
    ) -> None:
        self._default = default
        self._per_vendor = per_vendor or {}

    def for_vendor(self, vendor_id: str | None) -> Tolerances:
        return self._per_vendor.get(vendor_id or "", self._default)

    @classmethod
    def from_settings(cls, settings: Settings) -> ToleranceProvider:
        return cls(
            Tolerances(
                price_tolerance_pct=settings.price_tolerance_pct,
                qty_tolerance_pct=settings.qty_tolerance_pct,
                amount_tolerance_abs=Decimal(str(settings.amount_tolerance_abs)),
            )
        )
