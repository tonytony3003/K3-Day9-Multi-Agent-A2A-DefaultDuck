"""
Order & Seller Agent
====================
Retrieves order data from CSV and structures order status, items, sellers, and totals.
Handoff: provides order_info dict to downstream agents.
"""

from data_loader import OlistData
from llm_client import GroqLLMClient


class OrderAgent:
    """Analyzes order status, items, and seller information."""

    NAME = "OrderAgent"

    def __init__(self, data: OlistData, llm: GroqLLMClient | None = None):
        self.data = data
        self.llm = llm

    def analyze(self, order_id: str) -> dict:
        """Retrieve order data from CSV and structure order information."""
        order = self.data.get_order(order_id)
        if order is None:
            return {
                "order_id": order_id,
                "found": False,
                "order_status": None,
                "items": [],
                "seller_ids": [],
                "item_total": 0.0,
                "freight_total": 0.0,
                "analysis_summary": "Order not found.",
            }

        items_raw = self.data.get_items(order_id)
        items = []
        seller_ids_set: set[str] = set()
        item_total = 0.0
        freight_total = 0.0

        for it in items_raw:
            item_info = {
                "order_item_id": it["order_item_id"],
                "product_id": it.get("product_id", ""),
                "seller_id": it["seller_id"],
                "shipping_limit_date": it["shipping_limit_date"],
                "price": float(it["price"]),
                "freight_value": float(it["freight_value"]),
            }
            items.append(item_info)
            seller_ids_set.add(it["seller_id"])
            item_total += item_info["price"]
            freight_total += item_info["freight_value"]

        order_status = order.get("order_status", "")
        summary = f"Order {order_id} is in '{order_status}' status with {len(items)} items and {len(seller_ids_set)} sellers."

        return {
            "order_id": order_id,
            "found": True,
            "order_status": order_status,
            "order_purchase_timestamp": order.get("order_purchase_timestamp", ""),
            "order_approved_at": order.get("order_approved_at", ""),
            "order_delivered_carrier_date": order.get("order_delivered_carrier_date", "") or None,
            "order_delivered_customer_date": order.get("order_delivered_customer_date", "") or None,
            "order_estimated_delivery_date": order.get("order_estimated_delivery_date", "") or None,
            "items": items,
            "seller_ids": sorted(seller_ids_set),
            "item_total": round(item_total, 2),
            "freight_total": round(freight_total, 2),
            "llm_analysis": summary,
        }
