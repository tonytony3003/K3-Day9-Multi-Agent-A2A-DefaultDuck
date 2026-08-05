"""
Verifier Agent
==============
Uses LLM to validate the output JSON, check evidence IDs, and ensure schema compliance.
Writes the final output file.
"""

import json
import os

from llm_client import GroqLLMClient


SYSTEM_PROMPT = """You are a Verification Agent in an e-commerce dispute resolution system.
Your job is to validate a dispute resolution output JSON for correctness.

Check the following:
1. Evidence IDs follow the correct formats:
   - order:<order_id>
   - item:<order_id>:<order_item_id>
   - payment:<order_id>:<payment_sequential>
   - seller:<seller_id>
   - policy:<root_cause_code>
2. Array size limits: max 5 entity IDs, max 10 evidence IDs, max 3 root causes, max 3 responsible parties, max 5 actions
3. confidence is between 0 and 1
4. case_status is "action_required" if refund > 0, "no_action" if refund = 0
5. Financial values are rounded to 2 decimal places
6. All required fields are present

Return JSON with:
{
  "is_valid": true/false,
  "issues_found": ["list of issues if any"],
  "corrections": {"field_path": "corrected_value"} (if any corrections needed),
  "validation_summary": "brief summary"
}"""


class VerifierAgent:
    """Validates and writes the final dispute resolution output using LLM."""

    NAME = "VerifierAgent"

    MAX_ENTITY_IDS = 5
    MAX_EVIDENCE_IDS = 10
    MAX_ROOT_CAUSES = 3
    MAX_RESPONSIBLE_PARTIES = 3
    MAX_ACTIONS = 5

    def __init__(self, llm: GroqLLMClient):
        self.llm = llm

    def build_and_verify(
        self,
        case_id: str,
        order_info: dict,
        delivery_info: dict,
        payment_info: dict,
        policy_result: dict,
    ) -> dict:
        """Build the output JSON, validate with LLM, and return it."""
        order_id = order_info["order_id"]
        items = order_info.get("items", [])
        seller_ids = order_info.get("seller_ids", [])
        payment_rows = payment_info.get("payment_rows", [])

        # --- Build affected_entities ---
        order_ids = [order_id] if order_info.get("found") else []
        item_ids = [f"{order_id}:{it['order_item_id']}" for it in items]
        payment_ids = [f"{order_id}:{p['payment_sequential']}" for p in payment_rows]

        order_ids = order_ids[:self.MAX_ENTITY_IDS]
        item_ids = item_ids[:self.MAX_ENTITY_IDS]
        seller_ids_out = seller_ids[:self.MAX_ENTITY_IDS]
        payment_ids = payment_ids[:self.MAX_ENTITY_IDS]

        # --- Build evidence_ids ---
        evidence: list[str] = []
        if order_info.get("found"):
            evidence.append(f"order:{order_id}")
        for it in items:
            eid = f"item:{order_id}:{it['order_item_id']}"
            if eid not in evidence:
                evidence.append(eid)
        for p in payment_rows:
            eid = f"payment:{order_id}:{p['payment_sequential']}"
            if eid not in evidence:
                evidence.append(eid)
        for sid in seller_ids:
            eid = f"seller:{sid}"
            if eid not in evidence:
                evidence.append(eid)
        root_cause = policy_result.get("root_cause_code", "")
        if root_cause:
            eid = f"policy:{root_cause}"
            if eid not in evidence:
                evidence.append(eid)
        evidence = evidence[:self.MAX_EVIDENCE_IDS]

        # --- Build output ---
        item_total = order_info.get("item_total", 0.0)
        freight_total = order_info.get("freight_total", 0.0)
        payment_total = payment_info.get("payment_total", 0.0)
        recommended_refund = policy_result.get("recommended_refund", 0.0)
        responsible_parties = policy_result.get("responsible_parties", [])[:self.MAX_RESPONSIBLE_PARTIES]
        ranked_causes = [{"cause_code": root_cause, "rank": 1}]

        output = {
            "case_id": case_id,
            "assessment": {
                "primary_issue": policy_result["primary_issue"],
                "case_status": policy_result["case_status"],
                "confidence": policy_result["confidence"],
            },
            "affected_entities": {
                "order_ids": order_ids,
                "item_ids": item_ids,
                "seller_ids": seller_ids_out,
                "payment_ids": payment_ids,
            },
            "root_cause_analysis": {
                "ranked_causes": ranked_causes[:self.MAX_ROOT_CAUSES],
                "responsible_parties": responsible_parties,
            },
            "evidence_ids": evidence,
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": round(item_total, 2),
                "freight_total_brl": round(freight_total, 2),
                "payment_total_brl": round(payment_total, 2),
                "recommended_refund_brl": round(recommended_refund, 2),
            },
            "resolution_actions": policy_result.get("resolution_actions", [])[:self.MAX_ACTIONS],
        }

        # --- LLM Validation ---
        user_prompt = f"""Validate this dispute resolution output JSON:

{json.dumps(output, indent=2)}

Check all evidence IDs, array sizes, field types, and financial consistency."""

        try:
            llm_result = self.llm.call_json(SYSTEM_PROMPT, user_prompt)
            is_valid = llm_result.get("is_valid", True)
            validation_summary = llm_result.get("validation_summary", "")

            # Apply any corrections suggested by LLM
            if not is_valid:
                corrections = llm_result.get("corrections", {})
                if "case_status" in corrections:
                    output["assessment"]["case_status"] = corrections["case_status"]
                if "confidence" in corrections:
                    output["assessment"]["confidence"] = float(corrections["confidence"])
        except Exception:
            validation_summary = "LLM validation skipped due to error."

        # Final programmatic safeguards
        conf = output["assessment"]["confidence"]
        output["assessment"]["confidence"] = max(0.0, min(1.0, float(conf)))

        if output["financial_resolution"]["recommended_refund_brl"] > 0:
            output["assessment"]["case_status"] = "action_required"
        else:
            output["assessment"]["case_status"] = "no_action"

        return output

    @staticmethod
    def write_output(output: dict, output_dir: str) -> str:
        """Write the output dict to a JSON file."""
        case_id = output["case_id"]
        filename = f"{case_id}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        return filepath
