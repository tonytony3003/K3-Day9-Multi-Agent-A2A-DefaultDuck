"""
Payment Agent
=============
Reconciles payment rows against order item totals and detects split payment scenarios.
"""

from data_loader import OlistData
from llm_client import GroqLLMClient


class PaymentAgent:
    """Analyzes payment data and reconciles against order items."""

    NAME = "PaymentAgent"

    def __init__(self, data: OlistData, llm: GroqLLMClient | None = None):
        self.data = data
        self.llm = llm

    def analyze(self, order_id: str, order_info: dict) -> dict:
        """
        Analyze payment data for the given order.

        Returns:
            dict with payment analysis results
        """
        payments_raw = self.data.get_payments(order_id)
        payment_total = 0.0
        payment_rows = []

        for p in payments_raw:
            val = float(p["payment_value"])
            payment_total += val
            payment_rows.append({
                "payment_sequential": p["payment_sequential"],
                "payment_type": p.get("payment_type", ""),
                "payment_installments": p.get("payment_installments", ""),
                "payment_value": round(val, 2),
            })

        payment_total = round(payment_total, 2)
        item_total = order_info.get("item_total", 0.0)
        freight_total = order_info.get("freight_total", 0.0)
        expected_total = round(item_total + freight_total, 2)
        difference = round(abs(payment_total - expected_total), 2)
        is_reconciled = difference <= 0.10
        has_split = len(payment_rows) >= 2

        reasoning = f"Total paid {payment_total} BRL across {len(payment_rows)} payment rows vs expected {expected_total} BRL."

        return {
            "payment_total": payment_total,
            "num_payments": len(payment_rows),
            "payment_rows": payment_rows,
            "item_total": item_total,
            "freight_total": freight_total,
            "expected_total": expected_total,
            "is_reconciled": is_reconciled,
            "has_split_payment": has_split,
            "difference": difference,
            "llm_reasoning": reasoning,
        }
