from __future__ import annotations

from decimal import Decimal

from .data_catalog import DataCatalog
from .models import (
    AffectedEntities,
    Assessment,
    FinancialResolution,
    InputCase,
    OutputCase,
    RankedCause,
    ResponsibleParty,
    RootCauseAnalysis,
)


POLICY = {
    "canceled_order_paid": {
        "cause": "ORDER_CANCELED_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": "OLIST_PLATFORM",
        "action": "issue_full_refund",
        "confidence": 0.99,
    },
    "unavailable_order_paid": {
        "cause": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": "OLIST_PLATFORM",
        "action": "issue_full_refund",
        "confidence": 0.99,
    },
    "late_delivery_seller": {
        "cause": "SELLER_HANDOFF_AFTER_LIMIT",
        "party_type": "seller",
        "action": "refund_freight",
        "confidence": 0.98,
    },
    "late_delivery_logistics": {
        "cause": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "party_type": "logistics_provider",
        "party_id": "LOGISTICS_PROVIDER",
        "action": "refund_freight",
        "confidence": 0.97,
    },
    "valid_split_payment": {
        "cause": "MULTIPLE_PAYMENTS_RECONCILED",
        "action": "explain_valid_split_payment",
        "confidence": 0.98,
    },
    "unsupported_late_claim": {
        "cause": "DELIVERY_WITHIN_ESTIMATE",
        "action": "reject_late_refund",
        "confidence": 0.97,
    },
}


def specialist_findings(catalog: DataCatalog, order_id: str) -> dict[str, dict]:
    view = catalog.order_view(order_id)
    order, items, payments = view["order"], view["items"], view["payments"]
    violating_items = [
        item
        for item in items
        if order.order_delivered_carrier_date
        and order.order_delivered_carrier_date > item.shipping_limit_date
    ]
    delivered_late = bool(
        order.order_delivered_customer_date
        and order.order_delivered_customer_date > order.order_estimated_delivery_date
    )
    late_days = None
    if order.order_delivered_customer_date:
        late_days = round(
            (
                order.order_delivered_customer_date
                - order.order_estimated_delivery_date
            ).total_seconds()
            / 86400,
            2,
        )
    return {
        "order_seller": {
            "order_id": order_id,
            "order_status": order.order_status,
            "item_ids": [item.entity_id for item in items],
            "seller_ids": sorted({item.seller_id for item in items}),
            "violating_item_ids": [item.entity_id for item in violating_items],
            "violating_seller_ids": sorted({item.seller_id for item in violating_items}),
            "seller_handoff_late": bool(violating_items),
        },
        "payment": {
            "order_id": order_id,
            "payment_ids": [payment.entity_id for payment in payments],
            "payment_row_count": len(payments),
            "item_total_brl": str(view["item_total"]),
            "freight_total_brl": str(view["freight_total"]),
            "payment_total_brl": str(view["payment_total"]),
            "reconciliation_delta_brl": str(view["reconciliation_delta"]),
            "reconciled_within_0_10": abs(view["reconciliation_delta"])
            <= Decimal("0.10"),
            "has_split_payment": len(payments) >= 2,
        },
        "delivery": {
            "order_id": order_id,
            "delivered_customer_at": (
                order.order_delivered_customer_date.isoformat(sep=" ")
                if order.order_delivered_customer_date
                else None
            ),
            "estimated_delivery_at": order.order_estimated_delivery_date.isoformat(
                sep=" "
            ),
            "carrier_handoff_at": (
                order.order_delivered_carrier_date.isoformat(sep=" ")
                if order.order_delivered_carrier_date
                else None
            ),
            "delivered_late": delivered_late,
            "late_days": late_days,
            "seller_handoff_late": bool(violating_items),
            "violating_seller_ids": sorted({item.seller_id for item in violating_items}),
        },
    }


def evaluate_policy(findings: dict[str, dict]) -> str:
    order = findings["order_seller"]
    payment = findings["payment"]
    delivery = findings["delivery"]
    if order["order_status"] == "canceled" and Decimal(payment["payment_total_brl"]) > 0:
        return "canceled_order_paid"
    if order["order_status"] == "unavailable" and Decimal(payment["payment_total_brl"]) > 0:
        return "unavailable_order_paid"
    if delivery["delivered_late"] and delivery["seller_handoff_late"]:
        return "late_delivery_seller"
    if delivery["delivered_late"] and not delivery["seller_handoff_late"]:
        return "late_delivery_logistics"
    if payment["payment_row_count"] >= 2 and payment["reconciled_within_0_10"]:
        return "valid_split_payment"
    if delivery["delivered_customer_at"] and not delivery["delivered_late"] and payment["reconciled_within_0_10"]:
        return "unsupported_late_claim"
    raise ValueError(f"No EC_POLICY_V1 rule matched order {order['order_id']}")


def build_output(case: InputCase, catalog: DataCatalog) -> OutputCase:
    order_id = case.customer_request.claimed_order_id
    findings = specialist_findings(catalog, order_id)
    issue = evaluate_policy(findings)
    rule = POLICY[issue]
    view = catalog.order_view(order_id)
    item_ids = findings["order_seller"]["item_ids"][:5]
    seller_ids = findings["order_seller"]["seller_ids"][:5]
    payment_ids = findings["payment"]["payment_ids"][:5]

    parties: list[ResponsibleParty] = []
    if issue == "late_delivery_seller":
        parties = [
            ResponsibleParty(party_type="seller", party_id=seller_id)
            for seller_id in findings["delivery"]["violating_seller_ids"][:3]
        ]
    elif "party_type" in rule:
        parties = [
            ResponsibleParty(
                party_type=rule["party_type"], party_id=rule["party_id"]
            )
        ]

    if issue in {"canceled_order_paid", "unavailable_order_paid"}:
        refund = view["payment_total"]
    elif issue in {"late_delivery_seller", "late_delivery_logistics"}:
        refund = view["freight_total"]
    else:
        refund = Decimal("0.00")

    raw_evidence = [f"order:{order_id}"]
    raw_evidence.extend(f"item:{entity_id}" for entity_id in item_ids)
    raw_evidence.extend(f"payment:{entity_id}" for entity_id in payment_ids)
    raw_evidence.extend(
        f"seller:{party.party_id}"
        for party in parties
        if party.party_type == "seller"
    )
    evidence = raw_evidence[:9] + [f"policy:{rule['cause']}"]

    return OutputCase(
        case_id=case.case_id,
        assessment=Assessment(
            primary_issue=issue,
            case_status="action_required" if refund > 0 else "no_action",
            confidence=rule["confidence"],
        ),
        affected_entities=AffectedEntities(
            order_ids=[order_id],
            item_ids=item_ids,
            seller_ids=seller_ids,
            payment_ids=payment_ids,
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[RankedCause(cause_code=rule["cause"], rank=1)],
            responsible_parties=parties,
        ),
        evidence_ids=evidence,
        financial_resolution=FinancialResolution(
            currency="BRL",
            item_total_brl=float(view["item_total"]),
            freight_total_brl=float(view["freight_total"]),
            payment_total_brl=float(view["payment_total"]),
            recommended_refund_brl=float(refund),
        ),
        resolution_actions=[rule["action"]],
    )
