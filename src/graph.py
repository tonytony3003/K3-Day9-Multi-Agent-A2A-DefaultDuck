from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .data_catalog import DataCatalog
from .llm_client import MODEL_ID, OpenRouterClient
from .models import InputCase, OutputCase
from .policy_engine import build_output, specialist_findings
from .trace_logger import TraceLogger
from .validation import validate_output


class CaseState(TypedDict, total=False):
    case: InputCase
    plan: dict[str, Any]
    order_seller_finding: dict[str, Any]
    payment_finding: dict[str, Any]
    delivery_finding: dict[str, Any]
    draft: OutputCase
    verified_output: OutputCase
    errors: list[str]


SCOPES = {
    "coordinator": "plan and dispatch all three required specialist investigations",
    "order_seller_agent": "review order status, item, seller, and seller handoff facts",
    "payment_agent": "review payment aggregation and reconciliation facts",
    "delivery_agent": "review delivery timing and attribution facts",
    "policy_agent": "review the deterministic EC_POLICY_V1 decision and output artifact",
    "verifier_agent": "independently audit schema, evidence, finance, and policy invariants",
}


def build_graph(
    catalog: DataCatalog,
    tracer: TraceLogger,
    mode: str,
    client: OpenRouterClient | None,
):
    def review(agent: str, case_id: str, payload: dict) -> None:
        if mode == "llm":
            assert client is not None
            result, meta = client.review(agent, SCOPES[agent], payload)
            tracer.event(
                "agent_completed",
                case_id=case_id,
                agent=agent,
                payload=payload,
                summary={
                    "accepted": result.accepted,
                    "review_summary": result.summary,
                    "risk_flags": result.risk_flags,
                },
                model=MODEL_ID,
                provider=meta.provider,
                usage={
                    "prompt_tokens": meta.prompt_tokens,
                    "completion_tokens": meta.completion_tokens,
                    "total_tokens": meta.total_tokens,
                },
                latency_ms=meta.latency_ms,
                status="success" if result.accepted else "warning",
            )
        else:
            tracer.event(
                "agent_completed",
                case_id=case_id,
                agent=agent,
                payload=payload,
                summary={"accepted": True, "execution": "deterministic"},
            )

    def coordinator(state: CaseState) -> dict:
        case = state["case"]
        plan = {
            "claimed_order_id": case.customer_request.claimed_order_id,
            "policy_version": case.policy_version,
            "execution_mode": "parallel",
            "required_agents": [
                "order_seller_agent",
                "payment_agent",
                "delivery_agent",
            ],
        }
        review("coordinator", case.case_id, plan)
        return {"plan": plan}

    def specialist(key: str, agent: str, output_key: str):
        def node(state: CaseState) -> dict:
            case = state["case"]
            findings = specialist_findings(
                catalog, case.customer_request.claimed_order_id
            )[key]
            review(agent, case.case_id, findings)
            return {output_key: findings}

        return node

    def policy(state: CaseState) -> dict:
        case = state["case"]
        draft = build_output(case, catalog)
        review("policy_agent", case.case_id, draft.model_dump(mode="json"))
        return {"draft": draft}

    def verifier(state: CaseState) -> dict:
        case, draft = state["case"], state["draft"]
        errors = validate_output(case, draft, catalog)
        payload = {
            "case_id": case.case_id,
            "verdict": "PASS" if not errors else "FATAL",
            "errors": errors,
            "checked_rule": draft.assessment.primary_issue,
        }
        review("verifier_agent", case.case_id, payload)
        tracer.event(
            "verification_completed",
            case_id=case.case_id,
            agent="verifier_agent",
            payload=payload,
            summary={"verdict": payload["verdict"]},
            evidence_ids=draft.evidence_ids,
            status="success" if not errors else "error",
            error="; ".join(errors) if errors else None,
        )
        if errors:
            return {"errors": errors}
        return {"verified_output": draft, "errors": []}

    graph = StateGraph(CaseState)
    graph.add_node("coordinator", coordinator)
    graph.add_node(
        "order_seller",
        specialist("order_seller", "order_seller_agent", "order_seller_finding"),
    )
    graph.add_node(
        "payment", specialist("payment", "payment_agent", "payment_finding")
    )
    graph.add_node(
        "delivery", specialist("delivery", "delivery_agent", "delivery_finding")
    )
    graph.add_node("policy", policy)
    graph.add_node("verifier", verifier)
    graph.add_edge(START, "coordinator")
    graph.add_edge("coordinator", "order_seller")
    graph.add_edge("coordinator", "payment")
    graph.add_edge("coordinator", "delivery")
    graph.add_edge(["order_seller", "payment", "delivery"], "policy")
    graph.add_edge("policy", "verifier")
    graph.add_edge("verifier", END)
    return graph.compile()
