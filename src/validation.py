from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .data_catalog import DataCatalog
from .models import InputCase, OutputCase
from .policy_engine import build_output


def validate_output(case: InputCase, output: OutputCase, catalog: DataCatalog) -> list[str]:
    errors: list[str] = []
    expected = build_output(case, catalog)
    if output.model_dump() != expected.model_dump():
        errors.append("output differs from independently recomputed EC_POLICY_V1 result")
    if output.case_id != case.case_id:
        errors.append("case_id mismatch")
    if len(output.evidence_ids) != len(set(output.evidence_ids)):
        errors.append("duplicate evidence ID")
    for evidence_id in output.evidence_ids:
        if not catalog.evidence_exists(evidence_id):
            errors.append(f"evidence does not exist: {evidence_id}")
    refund = Decimal(str(output.financial_resolution.recommended_refund_brl))
    expected_status = "action_required" if refund > 0 else "no_action"
    if output.assessment.case_status != expected_status:
        errors.append("case_status does not match refund")
    return errors


def audit_submission(
    input_dir: Path, output_dir: Path, catalog: DataCatalog, expected_count: int = 50
) -> dict:
    input_files = sorted(input_dir.glob("EC_*.json"))
    output_files = sorted(output_dir.glob("EC_*.json"))
    errors: list[str] = []
    if len(input_files) != expected_count:
        errors.append(f"expected {expected_count} inputs, found {len(input_files)}")
    if [p.name for p in input_files] != [p.name for p in output_files]:
        errors.append("output filenames do not exactly match input filenames")
    issues: Counter[str] = Counter()
    refund = Decimal("0.00")
    case_ids: set[str] = set()
    for input_path in input_files:
        output_path = output_dir / input_path.name
        if not output_path.exists():
            continue
        case = InputCase.model_validate_json(input_path.read_text(encoding="utf-8"))
        output = OutputCase.model_validate_json(output_path.read_text(encoding="utf-8"))
        if case.case_id in case_ids:
            errors.append(f"duplicate case_id: {case.case_id}")
        case_ids.add(case.case_id)
        errors.extend(f"{case.case_id}: {error}" for error in validate_output(case, output, catalog))
        issues[output.assessment.primary_issue] += 1
        refund += Decimal(str(output.financial_resolution.recommended_refund_brl))
    return {
        "passed": not errors,
        "errors": errors,
        "input_count": len(input_files),
        "output_count": len(output_files),
        "issue_distribution": dict(sorted(issues.items())),
        "total_refund_brl": str(refund.quantize(Decimal("0.01"))),
    }


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)

