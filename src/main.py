from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from tqdm import tqdm

from .data_catalog import DataCatalog
from .graph import build_graph
from .llm_client import MODEL_ID, OpenRouterClient
from .models import InputCase
from .trace_logger import TraceLogger
from .validation import atomic_write_json, audit_submission


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the K3 Day 9 multi-agent dispute resolution pipeline."
    )
    parser.add_argument(
        "--mode",
        choices=("deterministic", "llm"),
        default="deterministic",
        help="Use OpenRouter agents only when explicitly selecting llm mode.",
    )
    parser.add_argument(
        "--case",
        help="Run one case ID such as EC_001. Omit to run and audit all 50 cases.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the tqdm progress bar (useful for CI or redirected logs).",
    )
    return parser.parse_args()


def load_cases(case_filter: str | None) -> list[tuple[Path, InputCase]]:
    paths = sorted((ROOT / "input").glob("EC_*.json"))
    cases = [
        (path, InputCase.model_validate_json(path.read_text(encoding="utf-8")))
        for path in paths
    ]
    if case_filter:
        cases = [(path, case) for path, case in cases if case.case_id == case_filter]
        if not cases:
            raise ValueError(f"Input case not found: {case_filter}")
    elif len(cases) != 50:
        raise ValueError(f"Expected exactly 50 input cases, found {len(cases)}")
    return cases


def write_metadata(mode: str, run_id: str, audit: dict | None) -> None:
    metadata = {
        "project": "K3 Day 09 Multi-Agent E-commerce Dispute Resolution",
        "run_id": run_id,
        "model": MODEL_ID,
        "model_provider": "OpenRouter",
        "parameter_size": "approved for this assignment",
        "framework": "LangGraph 1.0.10",
        "structured_output": "OpenRouter JSON Schema strict mode",
        "execution_mode": mode,
        "runtime": {
            "language": "Python",
            "python_version": platform.python_version(),
            "execution": "single process with parallel specialist graph branches",
        },
        "policy_version": "EC_POLICY_V1",
        "agent_count": 6,
        "agents": [
            "coordinator",
            "order_seller_agent",
            "payment_agent",
            "delivery_agent",
            "policy_agent",
            "verifier_agent",
        ],
        "data_snapshot": "Olist CSVs provided in repository",
        "audit": audit,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    atomic_write_json(ROOT / "logging" / "metadata.json", metadata)


def main() -> int:
    args = parse_args()
    cases = load_cases(args.case)
    config = dotenv_values(ROOT / ".env")
    client = None
    key_preflight = None
    if args.mode == "llm":
        client = OpenRouterClient(
            api_key=config.get("OPENROUTER_API_KEY") or "",
            configured_model=config.get("OPENROUTER_MODEL") or "",
        )
        print("Checking OpenRouter API key...", flush=True)
        key_preflight = client.preflight()
        print("OpenRouter API key: valid", flush=True)

    catalog = DataCatalog(ROOT / "data")
    for _, case in cases:
        if case.customer_request.claimed_order_id not in catalog.orders:
            raise ValueError(
                f"{case.case_id}: claimed order does not exist in source data"
            )

    run_id = f"run_{uuid4().hex}"
    tracer = TraceLogger(ROOT / "logging" / "trace.jsonl", run_id)
    tracer.event(
        "run_started",
        payload={
            "mode": args.mode,
            "case_count": len(cases),
            "key_preflight": key_preflight,
        },
        summary={"case_count": len(cases), "mode": args.mode},
        model=MODEL_ID if args.mode == "llm" else None,
    )
    tracer.event(
        "data_preflight_completed",
        payload={"orders_loaded": len(catalog.orders)},
        summary={"input_count": len(cases), "all_orders_found": True},
    )

    graph = build_graph(catalog, tracer, args.mode, client)
    issues: Counter[str] = Counter()
    progress = tqdm(
        cases,
        desc=f"Processing ({args.mode})",
        unit="case",
        dynamic_ncols=True,
        disable=args.no_progress,
    )
    for input_path, case in progress:
        progress.set_postfix_str(case.case_id, refresh=False)
        tracer.event(
            "case_started",
            case_id=case.case_id,
            payload=case.model_dump(mode="json"),
            summary={"claimed_order_id": case.customer_request.claimed_order_id},
        )
        try:
            result = graph.invoke({"case": case})
            errors = result.get("errors", [])
            if errors or "verified_output" not in result:
                raise RuntimeError("; ".join(errors) or "Verifier did not return output")
            output = result["verified_output"]
            atomic_write_json(
                ROOT / "output" / input_path.name, output.model_dump(mode="json")
            )
            issues[output.assessment.primary_issue] += 1
            tracer.event(
                "output_written",
                case_id=case.case_id,
                payload={"filename": input_path.name},
                summary={"primary_issue": output.assessment.primary_issue},
                evidence_ids=output.evidence_ids,
            )
            tracer.event(
                "case_completed",
                case_id=case.case_id,
                summary={"status": "verified"},
            )
        except Exception as exc:
            tracer.event(
                "case_completed",
                case_id=case.case_id,
                status="error",
                summary={"status": "failed"},
                error=str(exc),
            )
            write_metadata(args.mode, run_id, None)
            raise

    audit = None
    if not args.case:
        audit = audit_submission(ROOT / "input", ROOT / "output", catalog)
        if not audit["passed"]:
            raise RuntimeError("Submission audit failed: " + "; ".join(audit["errors"]))
    tracer.event(
        "run_completed",
        payload=audit or {"case": args.case},
        summary={
            "status": "passed",
            "issue_distribution": dict(sorted(issues.items())),
        },
    )
    write_metadata(args.mode, run_id, audit)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "mode": args.mode,
                "processed": len(cases),
                "issues": dict(sorted(issues.items())),
                "audit": audit,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
