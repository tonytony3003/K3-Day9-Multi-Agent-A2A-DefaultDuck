"""
PaymentAgent - Retrieves and analyzes payment information for an order.
Calculates total payment and validates against item + freight totals.
"""

from .data_loader import DataLoader


class PaymentAgent:
    """
    Responsible for:
    - Fetching all payment rows for an order
    - Computing total payment value
    - Detecting split payment scenarios
    - Cross-checking payment total vs item+freight total
    """

    TOLERANCE = 0.10  # BRL tolerance for reconciliation

    def __init__(self, data_loader: DataLoader):
        self.dl = data_loader

    def analyze(self, order_id: str, item_total: float, freight_total: float) -> dict:
        """
        Returns payment analysis for the given order.
        """
        result = {
            "agent": "PaymentAgent",
            "order_id": order_id,
            "payments": [],
            "payment_count": 0,
            "payment_total_brl": 0.0,
            "is_split_payment": False,
            "payment_matches_order": False,
            "payment_ids": [],
        }

        payments = self.dl.get_order_payments(order_id)
        result["payments"] = payments
        result["payment_count"] = len(payments)

        if not payments:
            return result

        total = sum(float(p.get("payment_value", 0.0)) for p in payments)
        result["payment_total_brl"] = round(total, 2)

        # Payment IDs: order_id:payment_sequential
        result["payment_ids"] = [
            f"{order_id}:{int(p.get('payment_sequential', 0))}"
            for p in payments
        ]

        # Split payment: 2 or more payment rows
        result["is_split_payment"] = len(payments) >= 2

        # Check if payment matches item + freight
        expected = item_total + freight_total
        diff = abs(total - expected)
        result["payment_matches_order"] = diff <= self.TOLERANCE

        return result
