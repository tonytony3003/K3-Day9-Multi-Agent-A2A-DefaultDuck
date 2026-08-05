from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


CENT = Decimal("0.01")


def money(value: str | Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_time(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class OrderRow:
    order_id: str
    customer_id: str
    order_status: str
    order_purchase_timestamp: datetime
    order_approved_at: datetime | None
    order_delivered_carrier_date: datetime | None
    order_delivered_customer_date: datetime | None
    order_estimated_delivery_date: datetime


@dataclass(frozen=True)
class ItemRow:
    order_id: str
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_date: datetime
    price: Decimal
    freight_value: Decimal

    @property
    def entity_id(self) -> str:
        return f"{self.order_id}:{self.order_item_id}"


@dataclass(frozen=True)
class PaymentRow:
    order_id: str
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: Decimal

    @property
    def entity_id(self) -> str:
        return f"{self.order_id}:{self.payment_sequential}"


class DataCatalog:
    """Read-only in-memory indexes for the three policy-critical Olist tables."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.orders: dict[str, OrderRow] = {}
        self.items_by_order: dict[str, list[ItemRow]] = {}
        self.payments_by_order: dict[str, list[PaymentRow]] = {}
        self.evidence_registry: set[str] = set()
        self._load()

    def _rows(self, name: str):
        with (self.data_dir / name).open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)

    def _load(self) -> None:
        for row in self._rows("olist_orders_dataset.csv"):
            order = OrderRow(
                order_id=row["order_id"],
                customer_id=row["customer_id"],
                order_status=row["order_status"],
                order_purchase_timestamp=parse_time(row["order_purchase_timestamp"]),
                order_approved_at=parse_time(row["order_approved_at"]),
                order_delivered_carrier_date=parse_time(row["order_delivered_carrier_date"]),
                order_delivered_customer_date=parse_time(row["order_delivered_customer_date"]),
                order_estimated_delivery_date=parse_time(row["order_estimated_delivery_date"]),
            )
            self.orders[order.order_id] = order
            self.evidence_registry.add(f"order:{order.order_id}")

        for row in self._rows("olist_order_items_dataset.csv"):
            item = ItemRow(
                order_id=row["order_id"],
                order_item_id=int(row["order_item_id"]),
                product_id=row["product_id"],
                seller_id=row["seller_id"],
                shipping_limit_date=parse_time(row["shipping_limit_date"]),
                price=money(row["price"]),
                freight_value=money(row["freight_value"]),
            )
            self.items_by_order.setdefault(item.order_id, []).append(item)
            self.evidence_registry.update(
                {f"item:{item.entity_id}", f"seller:{item.seller_id}"}
            )

        for row in self._rows("olist_order_payments_dataset.csv"):
            payment = PaymentRow(
                order_id=row["order_id"],
                payment_sequential=int(row["payment_sequential"]),
                payment_type=row["payment_type"],
                payment_installments=int(row["payment_installments"]),
                payment_value=money(row["payment_value"]),
            )
            self.payments_by_order.setdefault(payment.order_id, []).append(payment)
            self.evidence_registry.add(f"payment:{payment.entity_id}")

        for rows in self.items_by_order.values():
            rows.sort(key=lambda item: item.order_item_id)
        for rows in self.payments_by_order.values():
            rows.sort(key=lambda payment: payment.payment_sequential)

    def order_view(self, order_id: str) -> dict:
        if order_id not in self.orders:
            raise KeyError(f"Order not found: {order_id}")
        order = self.orders[order_id]
        items = self.items_by_order.get(order_id, [])
        payments = self.payments_by_order.get(order_id, [])
        item_total = money(sum((item.price for item in items), Decimal("0")))
        freight_total = money(sum((item.freight_value for item in items), Decimal("0")))
        payment_total = money(
            sum((payment.payment_value for payment in payments), Decimal("0"))
        )
        return {
            "order": order,
            "items": items,
            "payments": payments,
            "item_total": item_total,
            "freight_total": freight_total,
            "payment_total": payment_total,
            "reconciliation_delta": money(payment_total - item_total - freight_total),
        }

    def evidence_exists(self, evidence_id: str) -> bool:
        return evidence_id.startswith("policy:") or evidence_id in self.evidence_registry

