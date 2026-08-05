from decimal import Decimal
from pathlib import Path

import pytest

from src.data_catalog import DataCatalog
from src.models import AgentReview, InputCase
from src.policy_engine import build_output, evaluate_policy, specialist_findings
from src.validation import validate_output


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def catalog() -> DataCatalog:
    return DataCatalog(ROOT / "data")


def load_case(case_id: str) -> InputCase:
    return InputCase.model_validate_json(
        (ROOT / "input" / f"{case_id}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    ("case_id", "expected_issue"),
    [
        ("EC_001", "late_delivery_seller"),
        ("EC_003", "canceled_order_paid"),
        ("EC_004", "valid_split_payment"),
        ("EC_005", "unavailable_order_paid"),
        ("EC_009", "late_delivery_logistics"),
        ("EC_023", "unsupported_late_claim"),
    ],
)
def test_each_policy_branch(catalog: DataCatalog, case_id: str, expected_issue: str):
    case = load_case(case_id)
    output = build_output(case, catalog)
    assert output.assessment.primary_issue == expected_issue
    assert validate_output(case, output, catalog) == []


def test_unavailable_without_items_refunds_payment(catalog: DataCatalog):
    output = build_output(load_case("EC_005"), catalog)
    assert output.affected_entities.item_ids == []
    assert output.affected_entities.seller_ids == []
    assert output.financial_resolution.item_total_brl == 0
    assert output.financial_resolution.freight_total_brl == 0
    assert output.financial_resolution.recommended_refund_brl == 1191.5


def test_split_payment_is_summed_not_multiplied(catalog: DataCatalog):
    case = load_case("EC_030")
    findings = specialist_findings(catalog, case.customer_request.claimed_order_id)
    assert findings["payment"]["payment_row_count"] == 3
    assert Decimal(findings["payment"]["payment_total_brl"]) == Decimal("25.84")
    assert findings["payment"]["reconciled_within_0_10"] is True


def test_policy_precedence_canceled_over_split_payment():
    findings = {
        "order_seller": {"order_id": "x", "order_status": "canceled"},
        "payment": {
            "payment_total_brl": "100.00",
            "payment_row_count": 2,
            "reconciled_within_0_10": True,
        },
        "delivery": {
            "delivered_late": False,
            "seller_handoff_late": False,
            "delivered_customer_at": None,
        },
    }
    assert evaluate_policy(findings) == "canceled_order_paid"


def test_agent_review_schema_is_openai_strict_compatible():
    schema = AgentReview.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])


def test_late_delivery_seller_baseline_confidence(catalog: DataCatalog):
    output = build_output(load_case("EC_001"), catalog)
    assert output.assessment.primary_issue == "late_delivery_seller"
    assert output.assessment.confidence == 0.98
