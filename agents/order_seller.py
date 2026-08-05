"""
OrderSellerAgent - Retrieves order status, order items, and seller info.
Checks seller handoff timing against shipping_limit_date.
"""

from datetime import datetime
import math
from .data_loader import DataLoader


def _safe_str(val) -> str:
    """Convert a CSV value to str, returning '' for NaN/None/float-nan."""
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val).strip()


class OrderSellerAgent:
    """
    Responsible for:
    - Retrieving order metadata (status, timestamps)
    - Retrieving all order_items with freight and price info
    - Identifying which sellers are involved and their handoff timing
    """

    def __init__(self, data_loader: DataLoader):
        self.dl = data_loader

    def analyze(self, order_id: str) -> dict:
        """
        Returns a structured dict with all order/seller information.
        """
        result = {
            "agent": "OrderSellerAgent",
            "order_id": order_id,
            "order_found": False,
            "order_status": None,
            "order_purchase_timestamp": None,
            "order_approved_at": None,
            "order_delivered_carrier_date": None,
            "order_delivered_customer_date": None,
            "order_estimated_delivery_date": None,
            "items": [],
            "seller_ids": [],
            "item_total_brl": 0.0,
            "freight_total_brl": 0.0,
            "late_seller_handoff": False,
            "late_seller_ids": [],
        }

        # Fetch order
        order = self.dl.get_order(order_id)
        if order is None:
            return result

        result["order_found"] = True
        result["order_status"] = _safe_str(order.get("order_status", ""))
        result["order_purchase_timestamp"] = _safe_str(order.get("order_purchase_timestamp", ""))
        result["order_approved_at"] = _safe_str(order.get("order_approved_at", ""))
        result["order_delivered_carrier_date"] = _safe_str(order.get("order_delivered_carrier_date", ""))
        result["order_delivered_customer_date"] = _safe_str(order.get("order_delivered_customer_date", ""))
        result["order_estimated_delivery_date"] = _safe_str(order.get("order_estimated_delivery_date", ""))

        # Fetch items
        items = self.dl.get_order_items(order_id)
        result["items"] = items

        item_total = 0.0
        freight_total = 0.0
        seller_ids = set()
        late_seller_ids = set()

        carrier_date_str = result["order_delivered_carrier_date"]

        for item in items:
            seller_id = _safe_str(item.get("seller_id", ""))
            if seller_id:
                seller_ids.add(seller_id)

            price = float(item.get("price", 0.0) or 0.0)
            freight = float(item.get("freight_value", 0.0) or 0.0)
            item_total += price
            freight_total += freight

            # Check seller handoff timing
            shipping_limit_str = _safe_str(item.get("shipping_limit_date", ""))
            if carrier_date_str and shipping_limit_str:
                try:
                    carrier_dt = datetime.fromisoformat(
                        carrier_date_str.replace(" ", "T").rstrip("Z")
                    )
                    limit_dt = datetime.fromisoformat(
                        shipping_limit_str.replace(" ", "T").rstrip("Z")
                    )
                    if carrier_dt > limit_dt:
                        late_seller_ids.add(seller_id)
                        result["late_seller_handoff"] = True
                except (ValueError, TypeError):
                    pass

        result["item_total_brl"] = round(item_total, 2)
        result["freight_total_brl"] = round(freight_total, 2)
        result["seller_ids"] = sorted(list(seller_ids))
        result["late_seller_ids"] = sorted(list(late_seller_ids))

        return result
