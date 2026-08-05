"""
CoordinatorAgent - Orchestrates all sub-agents to resolve a single dispute case.

Flow:
  1. OrderSellerAgent → order/item/seller data + handoff timing
  2. PaymentAgent     → payment data + reconciliation
  3. DeliveryAgent    → delivery timing analysis
  4. PolicyAgent      → apply EC_POLICY_V1 → decision
  5. VerifierAgent    → validate + fix output schema
"""

import json
from datetime import datetime, timezone

from .data_loader import DataLoader
from .order_seller import OrderSellerAgent
from .payment import PaymentAgent
from .delivery import DeliveryAgent
from .policy import PolicyAgent
from .verifier import VerifierAgent


class CoordinatorAgent:
    """
    Orchestrates the multi-agent pipeline for each dispute case.
    Produces the final output JSON and a trace record.
    """

    def __init__(self, data_loader: DataLoader):
        self.dl = data_loader
        self.order_seller_agent = OrderSellerAgent(data_loader)
        self.payment_agent = PaymentAgent(data_loader)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent()

    def process_case(self, case_input: dict) -> tuple[dict, dict]:
        """
        Process a single dispute case through the full agent pipeline.

        Args:
            case_input: Parsed JSON from input/EC_XXX.json

        Returns:
            (output_json, trace_record)
        """
        case_id = case_input["case_id"]
        order_id = case_input["customer_request"]["claimed_order_id"]
        opened_at = case_input.get("opened_at", "")

        start_time = datetime.now(timezone.utc).isoformat()
        trace_steps = []

        print(f"[Coordinator] Processing {case_id} | order_id={order_id}")

        # ── Step 1: OrderSellerAgent ──────────────────────────────────────
        order_data = self.order_seller_agent.analyze(order_id)
        trace_steps.append({
            "step": 1,
            "agent": "OrderSellerAgent",
            "output_summary": {
                "order_found": order_data["order_found"],
                "order_status": order_data["order_status"],
                "item_count": len(order_data["items"]),
                "seller_count": len(order_data["seller_ids"]),
                "late_seller_handoff": order_data["late_seller_handoff"],
            }
        })

        # ── Step 2: PaymentAgent ──────────────────────────────────────────
        payment_data = self.payment_agent.analyze(
            order_id,
            order_data["item_total_brl"],
            order_data["freight_total_brl"],
        )
        trace_steps.append({
            "step": 2,
            "agent": "PaymentAgent",
            "output_summary": {
                "payment_count": payment_data["payment_count"],
                "payment_total_brl": payment_data["payment_total_brl"],
                "is_split_payment": payment_data["is_split_payment"],
                "payment_matches_order": payment_data["payment_matches_order"],
            }
        })

        # ── Step 3: DeliveryAgent ─────────────────────────────────────────
        delivery_data = self.delivery_agent.analyze(order_data)
        trace_steps.append({
            "step": 3,
            "agent": "DeliveryAgent",
            "output_summary": {
                "delivered_to_customer": delivery_data["delivered_to_customer"],
                "late_delivery_to_customer": delivery_data["late_delivery_to_customer"],
                "estimated": delivery_data["estimated_delivery_date"],
                "actual": delivery_data["actual_delivery_date"],
            }
        })

        # ── Step 4: PolicyAgent ───────────────────────────────────────────
        policy_data = self.policy_agent.analyze(order_data, payment_data, delivery_data)
        trace_steps.append({
            "step": 4,
            "agent": "PolicyAgent",
            "output_summary": {
                "primary_issue": policy_data["primary_issue"],
                "case_status": policy_data["case_status"],
                "root_cause_code": policy_data["root_cause_code"],
                "recommended_refund_brl": policy_data["recommended_refund_brl"],
                "resolution_actions": policy_data["resolution_actions"],
            }
        })

        # ── Assemble output ───────────────────────────────────────────────
        output = self._build_output(
            case_id, order_id, order_data, payment_data, delivery_data, policy_data
        )

        # ── Step 5: VerifierAgent ─────────────────────────────────────────
        output = self.verifier_agent.verify_and_fix(output)
        trace_steps.append({
            "step": 5,
            "agent": "VerifierAgent",
            "output_summary": {
                "evidence_ids_count": len(output["evidence_ids"]),
                "validated": True,
            }
        })

        end_time = datetime.now(timezone.utc).isoformat()

        # ── Build trace record ────────────────────────────────────────────
        trace = {
            "case_id": case_id,
            "order_id": order_id,
            "opened_at": opened_at,
            "processed_at_start": start_time,
            "processed_at_end": end_time,
            "steps": trace_steps,
            "final_decision": {
                "primary_issue": output["assessment"]["primary_issue"],
                "case_status": output["assessment"]["case_status"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
            }
        }

        return output, trace

    def _build_output(
        self,
        case_id: str,
        order_id: str,
        order_data: dict,
        payment_data: dict,
        delivery_data: dict,
        policy_data: dict,
    ) -> dict:
        """Constructs the final output JSON matching the required schema."""

        items = order_data.get("items", [])
        seller_ids = order_data.get("seller_ids", [])

        # item_ids: "order_id:order_item_id"
        item_ids = [
            f"{order_id}:{item.get('order_item_id', i+1)}"
            for i, item in enumerate(items)
        ][:5]

        # payment_ids: "order_id:payment_sequential"
        payment_ids = payment_data.get("payment_ids", [])[:5]

        # Build evidence IDs
        evidence_ids = self._build_evidence_ids(
            order_id, items, payment_data["payments"], seller_ids, policy_data["root_cause_code"]
        )

        # Root cause ranked_causes
        ranked_causes = []
        if policy_data["root_cause_code"]:
            ranked_causes = [{"cause_code": policy_data["root_cause_code"], "rank": 1}]

        output = {
            "case_id": case_id,
            "assessment": {
                "primary_issue": policy_data["primary_issue"],
                "case_status": policy_data["case_status"],
                "confidence": policy_data["confidence"],
            },
            "affected_entities": {
                "order_ids": [order_id] if order_data["order_found"] else [],
                "item_ids": item_ids,
                "seller_ids": seller_ids[:5],
                "payment_ids": payment_ids,
            },
            "root_cause_analysis": {
                "ranked_causes": ranked_causes[:3],
                "responsible_parties": policy_data["responsible_parties"][:3],
            },
            "evidence_ids": evidence_ids,
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": order_data["item_total_brl"],
                "freight_total_brl": order_data["freight_total_brl"],
                "payment_total_brl": payment_data["payment_total_brl"],
                "recommended_refund_brl": policy_data["recommended_refund_brl"],
            },
            "resolution_actions": policy_data["resolution_actions"][:5],
        }

        # If no items, set item/seller fields to empty per spec
        if not items:
            output["affected_entities"]["item_ids"] = []
            output["affected_entities"]["seller_ids"] = []
            output["financial_resolution"]["item_total_brl"] = 0.0
            output["financial_resolution"]["freight_total_brl"] = 0.0

        return output

    def _build_evidence_ids(
        self,
        order_id: str,
        items: list,
        payments: list,
        seller_ids: list,
        root_cause_code: str | None,
    ) -> list[str]:
        """Build a list of valid evidence IDs (max 10)."""
        evidence = []

        # order evidence
        evidence.append(f"order:{order_id}")

        # item evidences (up to 2)
        for item in items[:2]:
            item_seq = item.get("order_item_id", 1)
            evidence.append(f"item:{order_id}:{item_seq}")

        # payment evidences (up to 2)
        for pay in payments[:2]:
            seq = int(pay.get("payment_sequential", 0))
            evidence.append(f"payment:{order_id}:{seq}")

        # seller evidences (up to 2)
        for sid in seller_ids[:2]:
            evidence.append(f"seller:{sid}")

        # policy evidence
        if root_cause_code:
            evidence.append(f"policy:{root_cause_code}")

        return evidence[:10]
