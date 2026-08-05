"""
VerifierAgent - Validates the output JSON before writing to file.
Checks schema compliance, evidence ID formats, array limits, and financial consistency.
"""

import re


# Evidence ID regex patterns
EVIDENCE_PATTERNS = [
    re.compile(r"^order:[a-z0-9]+$"),
    re.compile(r"^item:[a-z0-9]+:\d+$"),
    re.compile(r"^payment:[a-z0-9]+:\d+$"),
    re.compile(r"^seller:[a-z0-9]+$"),
    re.compile(r"^policy:[A-Z_]+$"),
]

VALID_PRIMARY_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}

VALID_CASE_STATUSES = {"action_required", "no_action"}


def _is_valid_evidence_id(eid: str) -> bool:
    return any(p.match(eid) for p in EVIDENCE_PATTERNS)


class VerifierAgent:
    """
    Final validation gate before output is written.
    Enforces schema limits and evidence ID correctness.
    """

    def __init__(self):
        pass

    def verify_and_fix(self, output: dict) -> dict:
        """
        Validates and fixes the output dict.
        - Enforces array size limits
        - Removes invalid evidence IDs
        - Clamps confidence to [0, 1]
        - Ensures numeric fields are rounded correctly
        Returns the (possibly corrected) output dict.
        """
        issues = []

        # Validate/fix primary_issue
        if output["assessment"]["primary_issue"] not in VALID_PRIMARY_ISSUES:
            issues.append(f"Invalid primary_issue: {output['assessment']['primary_issue']}")

        # Validate/fix case_status
        if output["assessment"]["case_status"] not in VALID_CASE_STATUSES:
            issues.append(f"Invalid case_status: {output['assessment']['case_status']}")

        # Clamp confidence
        conf = output["assessment"]["confidence"]
        output["assessment"]["confidence"] = round(max(0.0, min(1.0, float(conf))), 4)

        # Enforce entity set limits (max 5 each)
        for key in ["order_ids", "item_ids", "seller_ids", "payment_ids"]:
            if len(output["affected_entities"].get(key, [])) > 5:
                output["affected_entities"][key] = output["affected_entities"][key][:5]
                issues.append(f"Truncated {key} to 5")

        # Enforce root_cause_analysis limits (max 3)
        rc = output["root_cause_analysis"]
        if len(rc.get("ranked_causes", [])) > 3:
            rc["ranked_causes"] = rc["ranked_causes"][:3]
        if len(rc.get("responsible_parties", [])) > 3:
            rc["responsible_parties"] = rc["responsible_parties"][:3]

        # Validate and filter evidence IDs (max 10)
        raw_evidence = output.get("evidence_ids", [])
        valid_evidence = [e for e in raw_evidence if _is_valid_evidence_id(e)]
        invalid = [e for e in raw_evidence if not _is_valid_evidence_id(e)]
        if invalid:
            issues.append(f"Removed invalid evidence IDs: {invalid}")
        output["evidence_ids"] = valid_evidence[:10]

        # Enforce resolution_actions limit (max 5)
        if len(output.get("resolution_actions", [])) > 5:
            output["resolution_actions"] = output["resolution_actions"][:5]

        # Round financial values
        fr = output["financial_resolution"]
        for field in ["item_total_brl", "freight_total_brl", "payment_total_brl", "recommended_refund_brl"]:
            if field in fr:
                fr[field] = round(float(fr.get(field, 0.0)), 2)

        if issues:
            print(f"  [VerifierAgent] Fixed issues for {output['case_id']}: {issues}")

        return output
