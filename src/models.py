from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerRequest(StrictModel):
    language: str
    message: str
    claimed_order_id: str


class InputCase(StrictModel):
    case_id: str
    opened_at: str
    customer_request: CustomerRequest
    policy_version: Literal["EC_POLICY_V1"]


PrimaryIssue = Literal[
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]


class Assessment(StrictModel):
    primary_issue: PrimaryIssue
    case_status: Literal["action_required", "no_action"]
    confidence: float = Field(ge=0, le=1)


class AffectedEntities(StrictModel):
    order_ids: list[str] = Field(max_length=5)
    item_ids: list[str] = Field(max_length=5)
    seller_ids: list[str] = Field(max_length=5)
    payment_ids: list[str] = Field(max_length=5)


class RankedCause(StrictModel):
    cause_code: str
    rank: int = Field(ge=1)


class ResponsibleParty(StrictModel):
    party_type: Literal["platform", "seller", "logistics_provider"]
    party_id: str


class RootCauseAnalysis(StrictModel):
    ranked_causes: list[RankedCause] = Field(max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(max_length=3)


class FinancialResolution(StrictModel):
    currency: Literal["BRL"]
    item_total_brl: float = Field(ge=0)
    freight_total_brl: float = Field(ge=0)
    payment_total_brl: float = Field(ge=0)
    recommended_refund_brl: float = Field(ge=0)


class OutputCase(StrictModel):
    case_id: str
    assessment: Assessment
    affected_entities: AffectedEntities
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: list[str] = Field(max_length=10)
    financial_resolution: FinancialResolution
    resolution_actions: list[str] = Field(max_length=5)


class AgentReview(StrictModel):
    accepted: bool
    summary: str = Field(max_length=240)
    # OpenAI strict structured outputs require every property to be listed in
    # `required`; callers return an empty array when there are no risks.
    risk_flags: list[str] = Field(max_length=5)
