"""
Policy Agent
============
Uses LLM to apply EC_POLICY_V1 business rules and determine the dispute resolution.
This is the core decision-making agent that receives evidence from all other agents.
"""

from llm_client import GroqLLMClient


SYSTEM_PROMPT = """You are the Policy Decision Agent in an e-commerce dispute resolution system.
You must apply the EC_POLICY_V1 rules to determine the correct resolution for a customer dispute.

CRITICAL: Apply rules in this EXACT priority order (highest first). Stop at the FIRST rule that matches:

Rule 1 - canceled_order_paid:
  Condition: order_status = "canceled" AND total_payment > 0
  Responsible: party_type="platform", party_id="OLIST_PLATFORM"
  Refund: total payment amount
  Action: "issue_full_refund"
  Root cause: "ORDER_CANCELED_AFTER_PAYMENT"

Rule 2 - unavailable_order_paid:
  Condition: order_status = "unavailable" AND total_payment > 0
  Responsible: party_type="platform", party_id="OLIST_PLATFORM"
  Refund: total payment amount
  Action: "issue_full_refund"
  Root cause: "ORDER_UNAVAILABLE_AFTER_PAYMENT"

Rule 3 - late_delivery_seller:
  Condition: delivery is late (delivered after estimated date) AND seller handed off late (carrier received after shipping_limit_date)
  Responsible: party_type="seller", party_id=the seller's ID
  Refund: total freight amount
  Action: "refund_freight"
  Root cause: "SELLER_HANDOFF_AFTER_LIMIT"

Rule 4 - late_delivery_logistics:
  Condition: delivery is late AND seller handed off on time (carrier received on or before shipping_limit_date)
  Responsible: party_type="logistics_provider", party_id="LOGISTICS_PROVIDER"
  Refund: total freight amount
  Action: "refund_freight"
  Root cause: "CARRIER_DELIVERED_AFTER_ESTIMATE"

Rule 5 - valid_split_payment:
  Condition: >= 2 payment rows AND payment total matches expected total (within 0.10 BRL)
  Responsible: none
  Refund: 0
  Action: "explain_valid_split_payment"
  Root cause: "MULTIPLE_PAYMENTS_RECONCILED"

Rule 6 - unsupported_late_claim:
  Condition: delivery is NOT late AND payment is reconciled
  Responsible: none
  Refund: 0
  Action: "reject_late_refund"
  Root cause: "DELIVERY_WITHIN_ESTIMATE"

IMPORTANT:
- case_status = "action_required" if refund > 0, otherwise "no_action"
- confidence should be between 0.90 and 0.98
- Round all monetary values to 2 decimal places

Return JSON with this EXACT structure:
{
  "primary_issue": "one of the 6 issue codes above",
  "case_status": "action_required" or "no_action",
  "confidence": number between 0 and 1,
  "root_cause_code": "one of the 6 root cause codes above",
  "responsible_parties": [{"party_type": "...", "party_id": "..."}],
  "recommended_refund": number,
  "resolution_actions": ["action_code"],
  "reasoning": "brief explanation of which rule matched and why"
}"""


class PolicyAgent:
    """Applies business rules using LLM to determine dispute resolution."""

    NAME = "PolicyAgent"

    def __init__(self, llm: GroqLLMClient):
        self.llm = llm

    def analyze(self, order_info: dict, delivery_info: dict, payment_info: dict) -> dict:
        """
        Use LLM to apply EC_POLICY_V1 rules based on evidence from other agents.

        Returns:
            dict with policy decision
        """
        order_status = order_info.get("order_status", "")
        payment_total = payment_info.get("payment_total", 0.0)
        freight_total = order_info.get("freight_total", 0.0)
        seller_ids = order_info.get("seller_ids", [])

        user_prompt = f"""Apply EC_POLICY_V1 rules to this case. Here is the evidence from other agents:

=== ORDER INFO ===
Order ID: {order_info.get('order_id')}
Order Status: {order_status}
Seller IDs: {seller_ids}
Item Total: {order_info.get('item_total', 0.0)} BRL
Freight Total: {freight_total} BRL

=== DELIVERY ANALYSIS ===
Is Delivered: {delivery_info.get('is_delivered')}
Is Late (delivered after estimated date): {delivery_info.get('is_late')}
Is Seller Late (carrier received after shipping limit): {delivery_info.get('is_seller_late')}
Late Seller IDs: {delivery_info.get('late_seller_ids', [])}
Delivered to Customer: {delivery_info.get('delivered_customer_date')}
Estimated Delivery: {delivery_info.get('estimated_delivery_date')}
Delivered to Carrier: {delivery_info.get('delivered_carrier_date')}

=== PAYMENT ANALYSIS ===
Payment Total: {payment_total} BRL
Number of Payment Rows: {payment_info.get('num_payments')}
Is Reconciled (payment matches order value within 0.10 BRL): {payment_info.get('is_reconciled')}
Has Split Payment (>= 2 rows): {payment_info.get('has_split_payment')}
Difference: {payment_info.get('difference')} BRL

Apply the rules in priority order and determine the resolution."""

        try:
            llm_result = self.llm.call_json(SYSTEM_PROMPT, user_prompt)

            primary_issue = llm_result.get("primary_issue", "unsupported_late_claim")
            case_status = llm_result.get("case_status", "no_action")
            confidence = llm_result.get("confidence", 0.90)
            root_cause_code = llm_result.get("root_cause_code", "DELIVERY_WITHIN_ESTIMATE")
            responsible_parties = llm_result.get("responsible_parties", [])
            recommended_refund = llm_result.get("recommended_refund", 0.0)
            resolution_actions = llm_result.get("resolution_actions", [])
            reasoning = llm_result.get("reasoning", "")

            # Validate and fix types
            if not isinstance(confidence, (int, float)):
                confidence = 0.90
            confidence = max(0.0, min(1.0, float(confidence)))

            if not isinstance(recommended_refund, (int, float)):
                recommended_refund = 0.0
            recommended_refund = round(float(recommended_refund), 2)

            if not isinstance(responsible_parties, list):
                responsible_parties = []

            if not isinstance(resolution_actions, list):
                resolution_actions = [resolution_actions] if resolution_actions else []

            # Validate case_status matches refund
            if recommended_refund > 0:
                case_status = "action_required"
            else:
                case_status = "no_action"

        except Exception as e:
            # Fallback: deterministic logic if LLM fails
            reasoning = f"LLM failed: {e}. Using deterministic fallback."
            result = self._fallback_logic(order_info, delivery_info, payment_info)
            result["reasoning"] = reasoning
            return result

        return {
            "primary_issue": primary_issue,
            "case_status": case_status,
            "confidence": confidence,
            "root_cause_code": root_cause_code,
            "responsible_parties": responsible_parties[:3],
            "recommended_refund": recommended_refund,
            "resolution_actions": resolution_actions[:5],
            "llm_reasoning": reasoning,
        }

    @staticmethod
    def _fallback_logic(order_info: dict, delivery_info: dict, payment_info: dict) -> dict:
        """Deterministic fallback if LLM call fails."""
        order_status = order_info.get("order_status", "")
        payment_total = payment_info.get("payment_total", 0.0)
        freight_total = order_info.get("freight_total", 0.0)
        is_late = delivery_info.get("is_late", False)
        is_seller_late = delivery_info.get("is_seller_late", False)
        has_split = payment_info.get("has_split_payment", False)
        is_reconciled = payment_info.get("is_reconciled", False)

        if order_status == "canceled" and payment_total > 0:
            return {"primary_issue": "canceled_order_paid", "case_status": "action_required",
                    "confidence": 0.95, "root_cause_code": "ORDER_CANCELED_AFTER_PAYMENT",
                    "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                    "recommended_refund": round(payment_total, 2), "resolution_actions": ["issue_full_refund"]}

        if order_status == "unavailable" and payment_total > 0:
            return {"primary_issue": "unavailable_order_paid", "case_status": "action_required",
                    "confidence": 0.95, "root_cause_code": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                    "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                    "recommended_refund": round(payment_total, 2), "resolution_actions": ["issue_full_refund"]}

        if is_late and is_seller_late:
            late_sellers = delivery_info.get("late_seller_ids", order_info.get("seller_ids", []))
            return {"primary_issue": "late_delivery_seller", "case_status": "action_required",
                    "confidence": 0.95, "root_cause_code": "SELLER_HANDOFF_AFTER_LIMIT",
                    "responsible_parties": [{"party_type": "seller", "party_id": s} for s in late_sellers[:3]],
                    "recommended_refund": round(freight_total, 2), "resolution_actions": ["refund_freight"]}

        if is_late and not is_seller_late:
            return {"primary_issue": "late_delivery_logistics", "case_status": "action_required",
                    "confidence": 0.95, "root_cause_code": "CARRIER_DELIVERED_AFTER_ESTIMATE",
                    "responsible_parties": [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
                    "recommended_refund": round(freight_total, 2), "resolution_actions": ["refund_freight"]}

        if has_split and is_reconciled:
            return {"primary_issue": "valid_split_payment", "case_status": "no_action",
                    "confidence": 0.95, "root_cause_code": "MULTIPLE_PAYMENTS_RECONCILED",
                    "responsible_parties": [], "recommended_refund": 0.0,
                    "resolution_actions": ["explain_valid_split_payment"]}

        return {"primary_issue": "unsupported_late_claim", "case_status": "no_action",
                "confidence": 0.90, "root_cause_code": "DELIVERY_WITHIN_ESTIMATE",
                "responsible_parties": [], "recommended_refund": 0.0,
                "resolution_actions": ["reject_late_refund"]}
