"""
PolicyAgent - Applies EC_POLICY_V1 business rules to determine:
  - primary_issue
  - responsible_parties
  - recommended_refund
  - resolution_actions
  - root_cause_code
"""


class PolicyAgent:
    """
    Applies business rules in priority order to determine the resolution.

    Priority (highest to lowest):
    1. canceled_order_paid
    2. unavailable_order_paid
    3. late_delivery_seller
    4. late_delivery_logistics
    5. valid_split_payment
    6. unsupported_late_claim
    """

    def __init__(self):
        pass

    def analyze(
        self,
        order_data: dict,
        payment_data: dict,
        delivery_data: dict,
    ) -> dict:
        """
        Applies EC_POLICY_V1 rules and returns a policy decision.

        Args:
            order_data:    Output from OrderSellerAgent.analyze()
            payment_data:  Output from PaymentAgent.analyze()
            delivery_data: Output from DeliveryAgent.analyze()

        Returns:
            dict with policy decision
        """
        result = {
            "agent": "PolicyAgent",
            "primary_issue": None,
            "case_status": "no_action",
            "confidence": 1.0,
            "root_cause_code": None,
            "responsible_parties": [],
            "recommended_refund_brl": 0.0,
            "resolution_actions": [],
        }

        order_status = order_data.get("order_status", "")
        payment_total = payment_data.get("payment_total_brl", 0.0)
        freight_total = order_data.get("freight_total_brl", 0.0)
        item_total = order_data.get("item_total_brl", 0.0)
        seller_ids = order_data.get("seller_ids", [])
        late_seller_ids = order_data.get("late_seller_ids", [])
        late_seller_handoff = order_data.get("late_seller_handoff", False)
        late_to_customer = delivery_data.get("late_delivery_to_customer", False)
        is_split_payment = payment_data.get("is_split_payment", False)
        payment_matches = payment_data.get("payment_matches_order", False)

        # Rule 1: canceled_order_paid
        if order_status == "canceled" and payment_total > 0:
            result["primary_issue"] = "canceled_order_paid"
            result["case_status"] = "action_required"
            result["root_cause_code"] = "ORDER_CANCELED_AFTER_PAYMENT"
            result["responsible_parties"] = [
                {"party_type": "platform", "party_id": "OLIST_PLATFORM"}
            ]
            result["recommended_refund_brl"] = round(payment_total, 2)
            result["resolution_actions"] = ["issue_full_refund"]
            result["confidence"] = 0.98
            return result

        # Rule 2: unavailable_order_paid
        if order_status == "unavailable" and payment_total > 0:
            result["primary_issue"] = "unavailable_order_paid"
            result["case_status"] = "action_required"
            result["root_cause_code"] = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
            result["responsible_parties"] = [
                {"party_type": "platform", "party_id": "OLIST_PLATFORM"}
            ]
            result["recommended_refund_brl"] = round(payment_total, 2)
            result["resolution_actions"] = ["issue_full_refund"]
            result["confidence"] = 0.98
            return result

        # Rule 3: late_delivery_seller
        # Condition: delivered late to customer AND seller handed off after shipping_limit_date
        if late_to_customer and late_seller_handoff and late_seller_ids:
            responsible = [
                {"party_type": "seller", "party_id": sid}
                for sid in late_seller_ids[:3]
            ]
            result["primary_issue"] = "late_delivery_seller"
            result["case_status"] = "action_required"
            result["root_cause_code"] = "SELLER_HANDOFF_AFTER_LIMIT"
            result["responsible_parties"] = responsible
            result["recommended_refund_brl"] = round(freight_total, 2)
            result["resolution_actions"] = ["refund_freight"]
            result["confidence"] = 0.93
            return result

        # Rule 4: late_delivery_logistics
        # Condition: delivered late to customer AND seller handed off on time
        if late_to_customer and not late_seller_handoff:
            result["primary_issue"] = "late_delivery_logistics"
            result["case_status"] = "action_required"
            result["root_cause_code"] = "CARRIER_DELIVERED_AFTER_ESTIMATE"
            result["responsible_parties"] = [
                {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
            ]
            result["recommended_refund_brl"] = round(freight_total, 2)
            result["resolution_actions"] = ["refund_freight"]
            result["confidence"] = 0.90
            return result

        # Rule 5: valid_split_payment
        # Condition: 2+ payment rows AND payment total matches item+freight within 0.10 BRL
        if is_split_payment and payment_matches:
            result["primary_issue"] = "valid_split_payment"
            result["case_status"] = "no_action"
            result["root_cause_code"] = "MULTIPLE_PAYMENTS_RECONCILED"
            result["responsible_parties"] = []
            result["recommended_refund_brl"] = 0.0
            result["resolution_actions"] = ["explain_valid_split_payment"]
            result["confidence"] = 0.92
            return result

        # Rule 6: unsupported_late_claim (default)
        # Order delivered on time or no actual late delivery
        result["primary_issue"] = "unsupported_late_claim"
        result["case_status"] = "no_action"
        result["root_cause_code"] = "DELIVERY_WITHIN_ESTIMATE"
        result["responsible_parties"] = []
        result["recommended_refund_brl"] = 0.0
        result["resolution_actions"] = ["reject_late_refund"]
        result["confidence"] = 0.88
        return result
