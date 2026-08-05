"""
DeliveryAgent - Compares actual delivery timestamps against estimated dates.
Determines whether a delivery was truly late and who is responsible.
"""

from datetime import datetime


class DeliveryAgent:
    """
    Responsible for:
    - Comparing order_delivered_customer_date vs order_estimated_delivery_date
    - Determining if delivery was late (to customer)
    - This works together with OrderSellerAgent's handoff check to assign blame
    """

    def __init__(self):
        pass

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse a date string to datetime, returning None on failure."""
        if not date_str or str(date_str).strip().lower() in ("nan", "nat", "", "none"):
            return None
        try:
            return datetime.fromisoformat(date_str.replace(" ", "T").rstrip("Z"))
        except (ValueError, TypeError):
            return None

    def analyze(self, order_data: dict) -> dict:
        """
        Analyzes delivery timing for the given order data (from OrderSellerAgent).

        Returns:
            dict with delivery analysis results
        """
        result = {
            "agent": "DeliveryAgent",
            "order_id": order_data.get("order_id"),
            "delivered_to_customer": False,
            "estimated_delivery_date": None,
            "actual_delivery_date": None,
            "carrier_received_date": None,
            "late_delivery_to_customer": False,
        }

        carrier_date_str = order_data.get("order_delivered_carrier_date", "")
        customer_date_str = order_data.get("order_delivered_customer_date", "")
        estimated_date_str = order_data.get("order_estimated_delivery_date", "")

        result["estimated_delivery_date"] = estimated_date_str
        result["actual_delivery_date"] = customer_date_str
        result["carrier_received_date"] = carrier_date_str

        customer_dt = self._parse_date(customer_date_str)
        estimated_dt = self._parse_date(estimated_date_str)

        if customer_dt is not None:
            result["delivered_to_customer"] = True

        # Late if delivered AFTER estimated date
        if customer_dt is not None and estimated_dt is not None:
            result["late_delivery_to_customer"] = customer_dt > estimated_dt

        return result
