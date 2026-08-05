"""
Main Entry Point
=================
Loads .env for API key, initializes Groq LLM client, then processes
all 50 cases through the multi-agent pipeline using llama-3.1-8b-instant.
Writes trace.jsonl immediately per case so audit logs stay live.
"""

import json
import os
import sys
import time
import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import OlistData
from llm_client import GroqLLMClient, MODEL_NAME
from agents.coordinator_agent import CoordinatorAgent


def load_env(env_path: str) -> dict[str, str]:
    """Load .env file into a dict (simple parser, no pip install needed)."""
    env_vars: dict[str, str] = {}
    if not os.path.exists(env_path):
        return env_vars
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # --- Resolve paths ---
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    input_dir = os.path.join(project_root, "input")
    output_dir = os.path.join(project_root, "output")
    logging_dir = os.path.join(project_root, "logging")
    env_path = os.path.join(project_root, ".env")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logging_dir, exist_ok=True)

    # --- Load .env ---
    print("=" * 60, flush=True)
    print("Multi-Agent E-commerce Dispute Resolution System", flush=True)
    print(f"Model: {MODEL_NAME} (via Groq API)", flush=True)
    print("=" * 60, flush=True)

    env_vars = load_env(env_path)
    api_key = env_vars.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

    # --- Initialize LLM client ---
    print("\n[1/4] Initializing Groq LLM client...", flush=True)
    llm = GroqLLMClient(api_key)
    print(f"  → Model: {llm.model}", flush=True)
    print(f"  → API: Groq REST API", flush=True)

    # --- Load data ---
    print("\n[2/4] Loading Olist dataset...", flush=True)
    t0 = time.time()
    data = OlistData(data_dir)
    load_time = time.time() - t0
    print(f"  → Loaded in {load_time:.2f}s", flush=True)
    print(f"  → Orders: {len(data.orders):,}", flush=True)
    print(f"  → Order items: {sum(len(v) for v in data.order_items.values()):,}", flush=True)
    print(f"  → Payments: {sum(len(v) for v in data.order_payments.values()):,}", flush=True)
    print(f"  → Sellers: {len(data.sellers):,}", flush=True)

    # --- Initialize coordinator ---
    coordinator = CoordinatorAgent(data, llm, output_dir)

    # --- Process all cases ---
    print(f"\n[3/4] Processing cases from {input_dir}...", flush=True)
    case_files = sorted([
        f for f in os.listdir(input_dir)
        if f.startswith("EC_") and f.endswith(".json")
    ])
    print(f"  → Found {len(case_files)} cases", flush=True)

    trace_path = os.path.join(logging_dir, "trace.jsonl")
    trace_file = open(trace_path, "w", encoding="utf-8")

    all_traces: list[dict] = []
    results_summary: list[dict] = []
    t_start = time.time()

    for i, case_file in enumerate(case_files, 1):
        filepath = os.path.join(input_dir, case_file)
        with open(filepath, encoding="utf-8") as f:
            case = json.load(f)

        case_t0 = time.time()
        output, trace_entries = coordinator.process_case(case)
        case_time = time.time() - case_t0

        # Append and flush trace immediately
        for entry in trace_entries:
            trace_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        trace_file.flush()

        all_traces.extend(trace_entries)

        issue = output["assessment"]["primary_issue"]
        status = output["assessment"]["case_status"]
        refund = output["financial_resolution"]["recommended_refund_brl"]
        print(
            f"  [{i:2d}/50] {case['case_id']} → {issue:<28s} | {status:<16s} "
            f"| refund={refund:.2f} BRL | {case_time:.1f}s",
            flush=True,
        )

        results_summary.append({
            "case_id": case["case_id"],
            "primary_issue": issue,
            "case_status": status,
            "refund": refund,
        })

    trace_file.close()

    total_time = time.time() - t_start
    print(f"\n  → All {len(case_files)} cases processed in {total_time:.1f}s", flush=True)
    print(f"  → Total LLM calls: {llm.total_calls}", flush=True)
    print(f"  → Total tokens used: {llm.total_tokens:,}", flush=True)

    # --- Write metadata.json ---
    print(f"\n[4/4] Writing metadata file...", flush=True)
    metadata = {
        "model": MODEL_NAME,
        "model_parameter_size": "8B",
        "framework": "python-stdlib + groq-rest-api",
        "runtime": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "os": sys.platform,
            "data_load_time_seconds": round(load_time, 2),
            "processing_time_seconds": round(total_time, 2),
            "total_llm_calls": llm.total_calls,
            "total_tokens_used": llm.total_tokens,
        },
        "agents": [
            {"name": "CoordinatorAgent", "role": "Orchestration and case dispatch"},
            {"name": "OrderAgent", "role": "Order data retrieval + LLM analysis"},
            {"name": "DeliveryAgent", "role": "LLM-powered delivery timeliness analysis"},
            {"name": "PaymentAgent", "role": "Payment data retrieval + LLM reconciliation"},
            {"name": "PolicyAgent", "role": "LLM-powered EC_POLICY_V1 rule application"},
            {"name": "VerifierAgent", "role": "LLM-powered schema validation + output writing"},
        ],
        "policy_version": "EC_POLICY_V1",
        "api_provider": "Groq",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    metadata_path = os.path.join(logging_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  → metadata.json: written", flush=True)

    # --- Summary ---
    print("\n" + "=" * 60, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 60, flush=True)

    from collections import Counter
    issue_counts = Counter(r["primary_issue"] for r in results_summary)
    for issue, count in sorted(issue_counts.items()):
        print(f"  {issue:<30s}: {count:3d} cases", flush=True)

    total_refund = sum(r["refund"] for r in results_summary)
    action_count = sum(1 for r in results_summary if r["case_status"] == "action_required")
    print(f"\n  Total refund recommended: {total_refund:.2f} BRL", flush=True)
    print(f"  Cases requiring action:   {action_count}/{len(results_summary)}", flush=True)
    print(f"  Cases no action:          {len(results_summary) - action_count}/{len(results_summary)}", flush=True)
    print(f"  Total LLM calls:          {llm.total_calls}", flush=True)
    print(f"  Total tokens:             {llm.total_tokens:,}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
