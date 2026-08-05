"""
main.py - Entry point for the Multi-Agent E-commerce Dispute Resolution System

Processes all 50 cases in the input/ directory, writes:
  - output/EC_XXX.json  (one per case)
  - trace.jsonl         (all traces, one line per case)
"""

import json
import os
import glob
import sys

from dotenv import load_dotenv
from agents.data_loader import DataLoader
from agents.coordinator import CoordinatorAgent

# Load .env (for API keys if needed in future extensions)
load_dotenv()

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TRACE_PATH = os.path.join(BASE_DIR, "trace.jsonl")


def main():
    print("=" * 60)
    print("  Multi-Agent E-commerce Dispute Resolution System")
    print("  EC_POLICY_V1")
    print("=" * 60)

    # Load all CSV datasets
    data_loader = DataLoader(DATA_DIR)

    # Initialize coordinator
    coordinator = CoordinatorAgent(data_loader)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Collect and sort input files
    input_files = sorted(glob.glob(os.path.join(INPUT_DIR, "EC_*.json")))
    if not input_files:
        print("[ERROR] No input files found in input/ directory.")
        sys.exit(1)

    print(f"\nFound {len(input_files)} input cases to process.\n")

    traces = []
    success_count = 0
    error_count = 0

    for input_path in input_files:
        filename = os.path.basename(input_path)
        try:
            # Read input
            with open(input_path, "r", encoding="utf-8") as f:
                case_input = json.load(f)

            # Process through agent pipeline
            output, trace = coordinator.process_case(case_input)

            # Write output JSON
            output_path = os.path.join(OUTPUT_DIR, filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            traces.append(trace)
            success_count += 1

            primary = output["assessment"]["primary_issue"]
            refund = output["financial_resolution"]["recommended_refund_brl"]
            print(f"  [OK] {filename} -> {primary} | refund={refund} BRL")

        except Exception as e:
            print(f"  [ERR] {filename} -> ERROR: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()

    # Write trace.jsonl (overwrite, not append)
    with open(TRACE_PATH, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    print("\n" + "=" * 60)
    print(f"  Done! {success_count} success | {error_count} errors")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Trace:  {TRACE_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
