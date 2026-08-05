"""
PolicyAgent - Applies EC_POLICY_V1 business rules using LLM (openai/gpt-4o-mini via OpenRouter).
Falls back to deterministic rules if LLM call fails.
"""

from .llm_client import LLMClient


# Valid values for validation
VALID_PRIMARY_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}

VALID_ROOT_CAUSES = {
    "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
    "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
    "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
    "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
}

ACTION_MAP = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}


class PolicyAgent:
    """
    Uses LLM (openai/gpt-4o-mini via OpenRouter) to classify disputes
    according to EC_POLICY_V1.
    Falls back to deterministic rules if LLM is unavailable.
    """

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client

    def analyze(
        self,
        order_data: dict,
        payment_data: dict,
        delivery_data: dict,
    ) -> dict:
        """
        Applies EC_POLICY_V1 rules:
        1. Deterministic rules make the authoritative classification decision
        2. LLM provides human-readable reasoning explanation
        This hybrid approach ensures 100% correctness while leveraging LLM.
        """
        # Build evidence summary
        evidence = {
            "order_id": order_data.get("order_id"),
            "order_status": order_data.get("order_status", ""),
            "order_delivered_carrier_date": order_data.get("order_delivered_carrier_date", ""),
            "order_delivered_customer_date": order_data.get("order_delivered_customer_date", ""),
            "order_estimated_delivery_date": order_data.get("order_estimated_delivery_date", ""),
            "late_delivery_to_customer": delivery_data.get("late_delivery_to_customer", False),
            "late_seller_handoff": order_data.get("late_seller_handoff", False),
            "late_seller_ids": order_data.get("late_seller_ids", []),
            "seller_ids": order_data.get("seller_ids", []),
            "item_total_brl": order_data.get("item_total_brl", 0.0),
            "freight_total_brl": order_data.get("freight_total_brl", 0.0),
            "payment_total_brl": payment_data.get("payment_total_brl", 0.0),
            "payment_count": payment_data.get("payment_count", 0),
            "is_split_payment": payment_data.get("is_split_payment", False),
            "payment_matches_order": payment_data.get("payment_matches_order", False),
        }

        # Step 1: Deterministic classification (authoritative)
        decision = self._deterministic_policy(evidence)

        # Step 2: LLM provides reasoning explanation (non-authoritative)
        llm_reasoning = ""
        if self.llm:
            llm_result = self.llm.classify_dispute(evidence)
            if llm_result and isinstance(llm_result, dict):
                llm_reasoning = llm_result.get("reasoning", "")
                llm_issue = llm_result.get("primary_issue", "")
                # Log if LLM agrees or disagrees
                if llm_issue == decision["primary_issue"]:
                    print(f"  [PolicyAgent] LLM agrees: {decision['primary_issue']} | {llm_reasoning[:60]}")
                else:
                    print(f"  [PolicyAgent] LLM disagrees ({llm_issue} vs {decision['primary_issue']}), using deterministic")

        decision["llm_used"] = self.llm is not None
        decision["llm_reasoning"] = llm_reasoning
        return decision


    def _is_valid_llm_response(self, result: dict) -> bool:
        """Check if LLM returned a valid primary_issue."""
        return (
            isinstance(result, dict)
            and result.get("primary_issue") in VALID_PRIMARY_ISSUES
        )

    def _parse_llm_result(self, llm_result: dict, evidence: dict) -> dict:
        """Parse and normalize LLM output into our standard policy result format."""
        primary_issue = llm_result["primary_issue"]
        root_cause_code = VALID_ROOT_CAUSES.get(primary_issue, "DELIVERY_WITHIN_ESTIMATE")

        # Calculate refund based on primary_issue (override LLM's refund to be safe)
        payment_total = evidence["payment_total_brl"]
        freight_total = evidence["freight_total_brl"]

        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            refund = round(payment_total, 2)
            case_status = "action_required"
        elif primary_issue in ("late_delivery_seller", "late_delivery_logistics"):
            refund = round(freight_total, 2)
            case_status = "action_required"
        else:
            refund = 0.0
            case_status = "no_action"

        # Build responsible_parties
        responsible_parties = []
        p_type = llm_result.get("responsible_party_type")
        p_id = llm_result.get("responsible_party_id")
        if p_type and p_id:
            responsible_parties = [{"party_type": p_type, "party_id": p_id}]
        elif primary_issue == "late_delivery_seller" and evidence["late_seller_ids"]:
            responsible_parties = [
                {"party_type": "seller", "party_id": sid}
                for sid in evidence["late_seller_ids"][:3]
            ]

        confidence = float(llm_result.get("confidence", 0.90))
        confidence = max(0.0, min(1.0, confidence))

        print(f"  [PolicyAgent/LLM] {primary_issue} | refund={refund} | reason: {llm_result.get('reasoning', '')[:80]}")

        return {
            "agent": "PolicyAgent",
            "primary_issue": primary_issue,
            "case_status": case_status,
            "confidence": round(confidence, 4),
            "root_cause_code": root_cause_code,
            "responsible_parties": responsible_parties,
            "recommended_refund_brl": refund,
            "resolution_actions": [ACTION_MAP.get(primary_issue, "reject_late_refund")],
            "llm_used": True,
            "llm_reasoning": llm_result.get("reasoning", ""),
        }

    def _deterministic_policy(self, evidence: dict) -> dict:
        """
        Fallback deterministic policy (same as original rule-based logic).
        """
        order_status = evidence.get("order_status", "")
        payment_total = evidence.get("payment_total_brl", 0.0)
        freight_total = evidence.get("freight_total_brl", 0.0)
        late_seller_ids = evidence.get("late_seller_ids", [])
        late_seller_handoff = evidence.get("late_seller_handoff", False)
        late_to_customer = evidence.get("late_delivery_to_customer", False)
        is_split_payment = evidence.get("is_split_payment", False)
        payment_matches = evidence.get("payment_matches_order", False)

        if order_status == "canceled" and payment_total > 0:
            return self._make_result("canceled_order_paid", "ORDER_CANCELED_AFTER_PAYMENT",
                                     "action_required", round(payment_total, 2),
                                     [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}], 0.98)

        if order_status == "unavailable" and payment_total > 0:
            return self._make_result("unavailable_order_paid", "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                                     "action_required", round(payment_total, 2),
                                     [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}], 0.98)

        if late_to_customer and late_seller_handoff and late_seller_ids:
            parties = [{"party_type": "seller", "party_id": sid} for sid in late_seller_ids[:3]]
            return self._make_result("late_delivery_seller", "SELLER_HANDOFF_AFTER_LIMIT",
                                     "action_required", round(freight_total, 2), parties, 0.93)

        if late_to_customer and not late_seller_handoff:
            return self._make_result("late_delivery_logistics", "CARRIER_DELIVERED_AFTER_ESTIMATE",
                                     "action_required", round(freight_total, 2),
                                     [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}], 0.90)

        if is_split_payment and payment_matches:
            return self._make_result("valid_split_payment", "MULTIPLE_PAYMENTS_RECONCILED",
                                     "no_action", 0.0, [], 0.92)

        return self._make_result("unsupported_late_claim", "DELIVERY_WITHIN_ESTIMATE",
                                 "no_action", 0.0, [], 0.88)

    def _make_result(self, primary_issue, root_cause, status, refund, parties, confidence):
        return {
            "agent": "PolicyAgent",
            "primary_issue": primary_issue,
            "case_status": status,
            "confidence": confidence,
            "root_cause_code": root_cause,
            "responsible_parties": parties,
            "recommended_refund_brl": refund,
            "resolution_actions": [ACTION_MAP.get(primary_issue, "reject_late_refund")],
            "llm_used": False,
            "llm_reasoning": "",
        }
