"""
Delivery Agent
==============
Analyzes delivery timestamps and determines if delivery was late
and who is responsible (seller vs logistics provider).
"""

from llm_client import GroqLLMClient


class DeliveryAgent:
    """Analyzes delivery timeliness and responsibility."""

    NAME = "DeliveryAgent"

    def __init__(self, llm: GroqLLMClient | None = None):
        self.llm = llm

    def analyze(self, order_info: dict) -> dict:
        """
        Analyze delivery timing from order_info.

        Returns:
            dict with delivery analysis results
        """
        delivered_customer = order_info.get("order_delivered_customer_date")
        estimated_delivery = order_info.get("order_estimated_delivery_date")
        delivered_carrier = order_info.get("order_delivered_carrier_date")
        items = order_info.get("items", [])

        is_delivered = delivered_customer is not None and delivered_customer != ""

        # Determine lateness
        is_late = False
        if is_delivered and estimated_delivery:
            is_late = delivered_customer > estimated_delivery

        # Determine seller handoff lateness
        is_seller_late = False
        late_seller_ids: list[str] = []
        shipping_limits = []

        for item in items:
            limit_date = item.get("shipping_limit_date", "")
            seller_id = item.get("seller_id", "")
            shipping_limits.append({
                "seller_id": seller_id,
                "shipping_limit_date": limit_date,
                "order_item_id": item.get("order_item_id", ""),
            })

            if delivered_carrier and limit_date:
                if delivered_carrier > limit_date:
                    is_seller_late = True
                    if seller_id and seller_id not in late_seller_ids:
                        late_seller_ids.append(seller_id)

        if not is_delivered:
            reasoning = "Order not delivered to customer yet."
        elif is_late:
            reasoning = f"Late delivery: Delivered on {delivered_customer}, estimated by {estimated_delivery}."
        else:
            reasoning = f"On-time delivery: Delivered on {delivered_customer}, within estimate {estimated_delivery}."

        return {
            "is_delivered": is_delivered,
            "is_late": is_late,
            "is_seller_late": is_seller_late,
            "late_seller_ids": late_seller_ids,
            "delivered_customer_date": delivered_customer,
            "estimated_delivery_date": estimated_delivery,
            "delivered_carrier_date": delivered_carrier,
            "shipping_limits": shipping_limits,
            "llm_reasoning": reasoning,
        }
