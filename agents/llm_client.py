"""
LLMClient - Thin wrapper around OpenRouter API using raw HTTP requests.
Used by PolicyAgent to call openai/gpt-4o-mini for dispute classification.
"""

import os
import json
import time
import urllib.request
import urllib.error


MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# System prompt for the PolicyAgent
SYSTEM_PROMPT = """You are an expert e-commerce dispute resolution agent following EC_POLICY_V1.

Apply rules in STRICT PRIORITY ORDER (stop at first match):

RULE 1 - canceled_order_paid:
  IF order_status = "canceled" AND payment_total > 0
  THEN primary_issue = "canceled_order_paid", refund = payment_total_brl (FULL), action = issue_full_refund

RULE 2 - unavailable_order_paid:
  IF order_status = "unavailable" AND payment_total > 0
  THEN primary_issue = "unavailable_order_paid", refund = payment_total_brl (FULL), action = issue_full_refund

RULE 3 - late_delivery_seller:
  IF late_delivery_to_customer = True AND late_seller_handoff = True
  THEN primary_issue = "late_delivery_seller", refund = freight_total_brl ONLY, action = refund_freight
  responsible_party = seller (use the seller_id from late_seller_ids)

RULE 4 - late_delivery_logistics:
  IF late_delivery_to_customer = True AND late_seller_handoff = False
  THEN primary_issue = "late_delivery_logistics", refund = freight_total_brl ONLY, action = refund_freight
  responsible_party = logistics_provider (LOGISTICS_PROVIDER)
  NOTE: This means the SELLER was on time but the CARRIER delivered late → logistics company is at fault → customer still gets freight refund!

RULE 5 - valid_split_payment:
  IF payment_count >= 2 AND payment_matches_order = True (within 0.10 BRL)
  THEN primary_issue = "valid_split_payment", refund = 0, action = explain_valid_split_payment

RULE 6 - unsupported_late_claim (DEFAULT):
  IF none of above rules match
  THEN primary_issue = "unsupported_late_claim", refund = 0, action = reject_late_refund

CRITICAL EXAMPLES:
- late_delivery_to_customer=True, late_seller_handoff=False → RULE 4 (late_delivery_logistics), NOT unsupported_late_claim!
- late_delivery_to_customer=True, late_seller_handoff=True → RULE 3 (late_delivery_seller)
- late_delivery_to_customer=False → skip rules 3 and 4

Root cause codes:
- canceled_order_paid → ORDER_CANCELED_AFTER_PAYMENT
- unavailable_order_paid → ORDER_UNAVAILABLE_AFTER_PAYMENT
- late_delivery_seller → SELLER_HANDOFF_AFTER_LIMIT
- late_delivery_logistics → CARRIER_DELIVERED_AFTER_ESTIMATE
- valid_split_payment → MULTIPLE_PAYMENTS_RECONCILED
- unsupported_late_claim → DELIVERY_WITHIN_ESTIMATE

Respond with ONLY valid JSON, no extra text:
{
  "primary_issue": "<one of the 6 values>",
  "root_cause_code": "<matching root cause code>",
  "case_status": "action_required" or "no_action",
  "recommended_refund_brl": <float>,
  "resolution_action": "<action string>",
  "responsible_party_type": "<party_type or null>",
  "responsible_party_id": "<party_id or null>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief 1-sentence explanation referencing which rule number matched>"
}"""


class LLMClient:
    """
    Wraps OpenRouter API calls with retry logic using raw HTTP requests.
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")

        self.api_key = api_key
        self.model = MODEL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/tonytony3003/K3-Day9-Multi-Agent-A2A-DefaultDuck",
            "X-Title": "K3-Day9-Multi-Agent-Dispute-Resolution",
        }
        print(f"[LLMClient] Using model: {self.model} via OpenRouter")

    def classify_dispute(self, evidence_summary: dict, max_retries: int = 3) -> dict | None:
        """
        Calls the LLM to classify a dispute case.

        Args:
            evidence_summary: dict with all evidence from data agents
            max_retries: number of retry attempts on failure

        Returns:
            Parsed dict from LLM response, or None on failure
        """
        user_message = f"""Analyze this e-commerce dispute and classify it according to EC_POLICY_V1:

ORDER EVIDENCE:
- order_id: {evidence_summary.get('order_id')}
- order_status: {evidence_summary.get('order_status')}
- order_delivered_carrier_date: {evidence_summary.get('order_delivered_carrier_date') or 'N/A'}
- order_delivered_customer_date: {evidence_summary.get('order_delivered_customer_date') or 'N/A'}
- order_estimated_delivery_date: {evidence_summary.get('order_estimated_delivery_date') or 'N/A'}

TIMING ANALYSIS:
- late_delivery_to_customer: {evidence_summary.get('late_delivery_to_customer')}
- late_seller_handoff: {evidence_summary.get('late_seller_handoff')}
- late_seller_ids: {evidence_summary.get('late_seller_ids')}

FINANCIAL DATA:
- item_total_brl: {evidence_summary.get('item_total_brl')}
- freight_total_brl: {evidence_summary.get('freight_total_brl')}
- payment_total_brl: {evidence_summary.get('payment_total_brl')}
- payment_count: {evidence_summary.get('payment_count')}
- is_split_payment: {evidence_summary.get('is_split_payment')}
- payment_matches_order: {evidence_summary.get('payment_matches_order')}

SELLER INFO:
- seller_ids: {evidence_summary.get('seller_ids')}

Apply the rules in PRIORITY ORDER and return ONLY JSON classification."""

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    self.API_URL,
                    data=payload,
                    headers=self.headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    content = result["choices"][0]["message"]["content"]
                    return json.loads(content)

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8")
                print(f"  [LLMClient] Attempt {attempt+1}/{max_retries} HTTP {e.code}: {err_body[:100]}")
                if e.code in (401, 403):
                    break  # No point retrying auth errors
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [LLMClient] Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

