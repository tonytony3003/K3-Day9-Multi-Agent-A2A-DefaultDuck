"""
DataLoader Agent - Loads and caches all CSV datasets into memory.
Provides fast lookup by order_id for downstream agents.
"""

import os
import pandas as pd
from functools import lru_cache


class DataLoader:
    """
    Loads all Olist CSV datasets once at startup and caches them.
    Provides query helpers for downstream agents.
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        print("[DataLoader] Loading CSV datasets...")
        self._load_all()
        print("[DataLoader] All datasets loaded successfully.")

    def _load_all(self):
        """Load all CSV files into memory."""
        def load(filename):
            path = os.path.join(self.data_dir, filename)
            return pd.read_csv(path, dtype=str)

        self.orders = load("olist_orders_dataset.csv")
        self.order_items = load("olist_order_items_dataset.csv")
        self.order_payments = load("olist_order_payments_dataset.csv")
        self.sellers = load("olist_sellers_dataset.csv")
        self.customers = load("olist_customers_dataset.csv")
        self.products = load("olist_products_dataset.csv")
        self.reviews = load("olist_order_reviews_dataset.csv")

        # Convert numeric columns for payments
        self.order_payments["payment_value"] = pd.to_numeric(
            self.order_payments["payment_value"], errors="coerce"
        ).fillna(0.0)
        self.order_payments["payment_sequential"] = pd.to_numeric(
            self.order_payments["payment_sequential"], errors="coerce"
        ).fillna(0).astype(int)
        self.order_payments["payment_installments"] = pd.to_numeric(
            self.order_payments["payment_installments"], errors="coerce"
        ).fillna(0).astype(int)

        # Convert numeric columns for order_items
        self.order_items["price"] = pd.to_numeric(
            self.order_items["price"], errors="coerce"
        ).fillna(0.0)
        self.order_items["freight_value"] = pd.to_numeric(
            self.order_items["freight_value"], errors="coerce"
        ).fillna(0.0)
        self.order_items["order_item_id"] = pd.to_numeric(
            self.order_items["order_item_id"], errors="coerce"
        ).fillna(0).astype(int)

    def get_order(self, order_id: str) -> dict | None:
        """Return the order row as a dict, or None if not found."""
        rows = self.orders[self.orders["order_id"] == order_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def get_order_items(self, order_id: str) -> list[dict]:
        """Return list of order_items rows for the given order_id."""
        rows = self.order_items[self.order_items["order_id"] == order_id]
        return rows.to_dict(orient="records")

    def get_order_payments(self, order_id: str) -> list[dict]:
        """Return list of order_payments rows for the given order_id."""
        rows = self.order_payments[self.order_payments["order_id"] == order_id]
        return rows.to_dict(orient="records")

    def get_seller(self, seller_id: str) -> dict | None:
        """Return seller row as dict, or None if not found."""
        rows = self.sellers[self.sellers["seller_id"] == seller_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()
