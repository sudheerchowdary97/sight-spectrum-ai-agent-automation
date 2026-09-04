"""ERP master-data generation: vendors, customers, POs, Goods Receipts, AR items.

All records are internally consistent (invoice → PO → GR share line structure)
and deterministic for a given seed. No heavy dependencies here beyond Faker, so
this module is cheap to import and test.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from faker import Faker

from invoice_agent.schemas import (
    ARItem,
    GoodsReceipt,
    GoodsReceiptLine,
    LineItem,
    PurchaseOrder,
)

# Fixed reference date so generated dates are reproducible (not wall-clock).
REFERENCE_DATE = date(2026, 9, 1)

# Small product catalogue: (sku, description, base_unit_price).
CATALOG: list[tuple[str, str, str]] = [
    ("SKU-1001", "A4 Copy Paper, 80gsm (ream)", "4.25"),
    ("SKU-1002", "Ballpoint Pens, Blue (box of 50)", "9.80"),
    ("SKU-1003", "Stapler, Heavy Duty", "14.50"),
    ("SKU-1004", "Toner Cartridge, Black", "78.00"),
    ("SKU-1005", "USB-C Cable, 2m", "11.25"),
    ("SKU-1006", "Wireless Mouse", "22.40"),
    ("SKU-1007", "Mechanical Keyboard", "64.90"),
    ("SKU-1008", '27" LED Monitor', "189.00"),
    ("SKU-1009", "Laptop Docking Station", "142.75"),
    ("SKU-1010", "Ergonomic Office Chair", "245.00"),
    ("SKU-1011", "Standing Desk, Electric", "410.00"),
    ("SKU-1012", "Desk Lamp, LED", "33.60"),
    ("SKU-1013", "Whiteboard, 120x90cm", "58.00"),
    ("SKU-1014", "Printer Paper, A3 (ream)", "7.90"),
    ("SKU-1015", "External SSD, 1TB", "96.50"),
    ("SKU-1016", "Webcam, 1080p", "48.00"),
    ("SKU-1017", "Noise-Cancelling Headset", "129.00"),
    ("SKU-1018", "Network Switch, 8-port", "72.30"),
    ("SKU-1019", "Surge Protector, 6-outlet", "19.99"),
    ("SKU-1020", "Label Printer", "88.00"),
    ("SKU-1021", "Coffee Beans, 1kg", "16.75"),
    ("SKU-1022", "Hand Sanitiser, 5L", "24.00"),
    ("SKU-1023", "Recycled Notebooks (pack of 10)", "12.50"),
    ("SKU-1024", "HDMI Cable, 3m", "8.40"),
]

TWO_CENTS = Decimal("0.01")


def money(value: Decimal | str | int) -> Decimal:
    """Quantise to 2 decimal places (banker-safe half-up)."""
    return Decimal(value).quantize(TWO_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Vendor:
    """A supplier that issues invoices."""

    vendor_id: str
    name: str
    email: str
    address: str
    iban: str


@dataclass(frozen=True)
class Customer:
    """A customer that sends remittances (AR mirror track)."""

    customer_id: str
    name: str
    email: str


@dataclass
class MasterData:
    """The full set of ERP master records plus lookup helpers."""

    vendors: list[Vendor]
    customers: list[Customer]
    purchase_orders: list[PurchaseOrder]
    goods_receipts: list[GoodsReceipt]
    ar_items: list[ARItem]

    @property
    def vendor_by_id(self) -> dict[str, Vendor]:
        return {v.vendor_id: v for v in self.vendors}

    @property
    def po_by_number(self) -> dict[str, PurchaseOrder]:
        return {po.po_number: po for po in self.purchase_orders}

    @property
    def gr_by_po(self) -> dict[str, GoodsReceipt]:
        return {gr.po_number: gr for gr in self.goods_receipts}


def _make_vendors(fake: Faker, count: int) -> list[Vendor]:
    vendors: list[Vendor] = []
    for i in range(count):
        name = fake.company()
        slug = "".join(ch for ch in name.lower() if ch.isalnum())[:12] or f"vendor{i}"
        vendors.append(
            Vendor(
                vendor_id=f"V-{1001 + i}",
                name=name,
                email=f"ap@{slug}.example",
                address=fake.address().replace("\n", ", "),
                iban=fake.iban(),
            )
        )
    return vendors


def _make_customers(fake: Faker, count: int) -> list[Customer]:
    customers: list[Customer] = []
    for i in range(count):
        name = fake.company()
        slug = "".join(ch for ch in name.lower() if ch.isalnum())[:12] or f"cust{i}"
        customers.append(
            Customer(
                customer_id=f"C-{2001 + i}",
                name=name,
                email=f"remittance@{slug}.example",
            )
        )
    return customers


def _make_po_lines(rng: random.Random) -> list[LineItem]:
    n_lines = rng.randint(1, 5)
    picks = rng.sample(CATALOG, n_lines)
    lines: list[LineItem] = []
    for idx, (sku, desc, base_price) in enumerate(picks, start=1):
        qty = Decimal(rng.randint(1, 40))
        # Small vendor-specific price drift so catalogues are not identical.
        unit_price = money(Decimal(base_price) * Decimal(rng.uniform(0.95, 1.08)))
        lines.append(
            LineItem(
                line_no=idx,
                sku=sku,
                description=desc,
                quantity=qty,
                unit_price=unit_price,
                amount=money(qty * unit_price),
            )
        )
    return lines


def _make_purchase_orders(
    rng: random.Random, vendors: list[Vendor], count: int
) -> list[PurchaseOrder]:
    pos: list[PurchaseOrder] = []
    for i in range(count):
        vendor = rng.choice(vendors)
        lines = _make_po_lines(rng)
        order_date = REFERENCE_DATE - timedelta(days=rng.randint(20, 120))
        pos.append(
            PurchaseOrder(
                po_number=f"PO-{10001 + i}",
                vendor_id=vendor.vendor_id,
                vendor_name=vendor.name,
                order_date=order_date,
                lines=lines,
                total_amount=money(sum((line.amount for line in lines), Decimal(0))),
            )
        )
    return pos


def _make_goods_receipts(
    rng: random.Random, purchase_orders: list[PurchaseOrder], gr_ratio: float
) -> list[GoodsReceipt]:
    """Create full Goods Receipts for a subset of POs (enables 3-way match).

    POs without a GR force the two-way path.
    """
    receipts: list[GoodsReceipt] = []
    gr_seq = 5001
    for po in purchase_orders:
        if rng.random() > gr_ratio:
            continue  # no receipt -> two-way-only
        receipts.append(
            GoodsReceipt(
                gr_number=f"GR-{gr_seq}",
                po_number=po.po_number,
                receipt_date=po.order_date + timedelta(days=rng.randint(2, 15)),
                lines=[
                    GoodsReceiptLine(
                        line_no=line.line_no,
                        sku=line.sku,
                        description=line.description,
                        quantity_received=line.quantity,  # full receipt
                    )
                    for line in po.lines
                ],
            )
        )
        gr_seq += 1
    return receipts


def _make_ar_items(rng: random.Random, customers: list[Customer], count: int) -> list[ARItem]:
    items: list[ARItem] = []
    for i in range(count):
        customer = rng.choice(customers)
        amount = money(Decimal(rng.uniform(150, 9500)))
        due = REFERENCE_DATE + timedelta(days=rng.randint(-30, 45))
        items.append(
            ARItem(
                ar_item_id=f"AR-{7001 + i}",
                customer_id=customer.customer_id,
                customer_name=customer.name,
                invoice_number=f"AR-INV-{40001 + i}",
                open_amount=amount,
                due_date=due,
            )
        )
    return items


def build_master(
    seed: int,
    *,
    num_vendors: int = 12,
    num_pos: int = 60,
    gr_ratio: float = 0.8,
    num_customers: int = 8,
    num_ar: int = 25,
) -> MasterData:
    """Build a deterministic set of ERP master records."""
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    vendors = _make_vendors(fake, num_vendors)
    customers = _make_customers(fake, num_customers)
    purchase_orders = _make_purchase_orders(rng, vendors, num_pos)
    goods_receipts = _make_goods_receipts(rng, purchase_orders, gr_ratio)
    ar_items = _make_ar_items(rng, customers, num_ar)

    return MasterData(
        vendors=vendors,
        customers=customers,
        purchase_orders=purchase_orders,
        goods_receipts=goods_receipts,
        ar_items=ar_items,
    )
