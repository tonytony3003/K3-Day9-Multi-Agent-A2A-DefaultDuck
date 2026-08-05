"""
Data Loader Module
==================
Loads Olist CSV datasets into in-memory dictionaries for fast O(1) lookup by order_id.
Only loads the 4 CSV files needed for dispute resolution:
- olist_orders_dataset.csv
- olist_order_items_dataset.csv
- olist_order_payments_dataset.csv
- olist_sellers_dataset.csv
"""

import csv
import os
from typing import Any


def _read_csv(filepath: str) -> list[dict[str, str]]:
    """Read a CSV file and return a list of dicts."""
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


class OlistData:
    """In-memory store for Olist dataset with O(1) lookup by order_id."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

        # --- Load orders: order_id -> order row ---
        orders_raw = _read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
        self.orders: dict[str, dict[str, str]] = {}
        for row in orders_raw:
            oid = row['order_id'].strip('"')
            # Clean all values
            cleaned = {k: v.strip('"') for k, v in row.items()}
            self.orders[oid] = cleaned

        # --- Load order_items: order_id -> list of item rows ---
        items_raw = _read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
        self.order_items: dict[str, list[dict[str, str]]] = {}
        for row in items_raw:
            oid = row['order_id'].strip('"')
            cleaned = {k: v.strip('"') for k, v in row.items()}
            self.order_items.setdefault(oid, []).append(cleaned)

        # --- Load order_payments: order_id -> list of payment rows ---
        payments_raw = _read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))
        self.order_payments: dict[str, list[dict[str, str]]] = {}
        for row in payments_raw:
            oid = row['order_id'].strip('"')
            cleaned = {k: v.strip('"') for k, v in row.items()}
            self.order_payments.setdefault(oid, []).append(cleaned)

        # --- Load sellers: seller_id -> seller row ---
        sellers_raw = _read_csv(os.path.join(data_dir, 'olist_sellers_dataset.csv'))
        self.sellers: dict[str, dict[str, str]] = {}
        for row in sellers_raw:
            sid = row['seller_id'].strip('"')
            cleaned = {k: v.strip('"') for k, v in row.items()}
            self.sellers[sid] = cleaned

    def get_order(self, order_id: str) -> dict[str, str] | None:
        """Get order data by order_id."""
        return self.orders.get(order_id)

    def get_items(self, order_id: str) -> list[dict[str, str]]:
        """Get all items for an order."""
        return self.order_items.get(order_id, [])

    def get_payments(self, order_id: str) -> list[dict[str, str]]:
        """Get all payment rows for an order."""
        return self.order_payments.get(order_id, [])

    def get_seller(self, seller_id: str) -> dict[str, str] | None:
        """Get seller data by seller_id."""
        return self.sellers.get(seller_id)
