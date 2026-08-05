"""
Coordinator Agent
=================
Top-level orchestrator that receives a case, dispatches to specialized agents,
collects results with LLM-powered analysis, and produces the final output.
"""

import json
import datetime
from typing import Any

from data_loader import OlistData
from llm_client import GroqLLMClient
from agents.order_agent import OrderAgent
from agents.delivery_agent import DeliveryAgent
from agents.payment_agent import PaymentAgent
from agents.policy_agent import PolicyAgent
from agents.verifier_agent import VerifierAgent


class CoordinatorAgent:
    """Orchestrates the multi-agent dispute resolution pipeline with LLM."""

    NAME = "CoordinatorAgent"

    def __init__(self, data: OlistData, llm: GroqLLMClient, output_dir: str):
        self.data = data
        self.llm = llm
        self.output_dir = output_dir

        # Initialize sub-agents with LLM
        self.order_agent = OrderAgent(data, llm)
        self.delivery_agent = DeliveryAgent(llm)
        self.payment_agent = PaymentAgent(data, llm)
        self.policy_agent = PolicyAgent(llm)
        self.verifier_agent = VerifierAgent(llm)

    def process_case(self, case: dict) -> tuple[dict, list[dict]]:
        """
        Process a single dispute case through the full agent pipeline.

        Returns:
            Tuple of (output_dict, trace_entries)
        """
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        trace: list[dict] = []

        # --- Step 1: Order Agent (data retrieval + LLM analysis) ---
        order_info = self.order_agent.analyze(order_id)
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=OrderAgent.NAME,
            action="analyze_order",
            input_data={"order_id": order_id},
            output_summary={
                "found": order_info["found"],
                "order_status": order_info.get("order_status"),
                "num_items": len(order_info.get("items", [])),
                "num_sellers": len(order_info.get("seller_ids", [])),
                "item_total": order_info.get("item_total"),
                "freight_total": order_info.get("freight_total"),
                "llm_analysis": order_info.get("llm_analysis", ""),
            },
        ))

        # --- Step 2: Delivery Agent (LLM-powered timing analysis) ---
        delivery_info = self.delivery_agent.analyze(order_info)
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=DeliveryAgent.NAME,
            action="analyze_delivery",
            input_data={"order_id": order_id},
            output_summary={
                "is_delivered": delivery_info["is_delivered"],
                "is_late": delivery_info["is_late"],
                "is_seller_late": delivery_info["is_seller_late"],
                "delivered_customer_date": delivery_info.get("delivered_customer_date"),
                "estimated_delivery_date": delivery_info.get("estimated_delivery_date"),
                "llm_reasoning": delivery_info.get("llm_reasoning", ""),
            },
        ))

        # --- Step 3: Payment Agent (data retrieval + LLM reconciliation) ---
        payment_info = self.payment_agent.analyze(order_id, order_info)
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=PaymentAgent.NAME,
            action="analyze_payment",
            input_data={"order_id": order_id},
            output_summary={
                "payment_total": payment_info["payment_total"],
                "num_payments": payment_info["num_payments"],
                "is_reconciled": payment_info["is_reconciled"],
                "has_split_payment": payment_info["has_split_payment"],
                "difference": payment_info["difference"],
                "llm_reasoning": payment_info.get("llm_reasoning", ""),
            },
        ))

        # --- Step 4: Policy Agent (LLM-powered rule application) ---
        policy_result = self.policy_agent.analyze(order_info, delivery_info, payment_info)
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=PolicyAgent.NAME,
            action="apply_policy",
            input_data={"order_id": order_id},
            output_summary={
                "primary_issue": policy_result["primary_issue"],
                "case_status": policy_result["case_status"],
                "root_cause_code": policy_result["root_cause_code"],
                "recommended_refund": policy_result["recommended_refund"],
                "resolution_actions": policy_result["resolution_actions"],
                "llm_reasoning": policy_result.get("llm_reasoning", ""),
            },
        ))

        # --- Step 5: Verifier Agent (LLM validation + write) ---
        output = self.verifier_agent.build_and_verify(
            case_id=case_id,
            order_info=order_info,
            delivery_info=delivery_info,
            payment_info=payment_info,
            policy_result=policy_result,
        )
        filepath = self.verifier_agent.write_output(output, self.output_dir)
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=VerifierAgent.NAME,
            action="verify_and_write",
            input_data={"case_id": case_id},
            output_summary={
                "output_file": filepath,
                "primary_issue": output["assessment"]["primary_issue"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
                "num_evidence": len(output["evidence_ids"]),
            },
        ))

        # --- Step 6: Coordinator summary ---
        trace.append(self._trace_entry(
            case_id=case_id,
            agent=self.NAME,
            action="case_completed",
            input_data={"case_id": case_id},
            output_summary={
                "primary_issue": output["assessment"]["primary_issue"],
                "case_status": output["assessment"]["case_status"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
            },
        ))

        return output, trace

    @staticmethod
    def _trace_entry(case_id: str, agent: str, action: str,
                     input_data: dict, output_summary: dict) -> dict:
        """Create a trace log entry."""
        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "case_id": case_id,
            "agent": agent,
            "action": action,
            "input": input_data,
            "output": output_summary,
        }
