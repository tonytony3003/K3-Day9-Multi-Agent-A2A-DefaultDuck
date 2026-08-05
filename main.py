import os
import json
import glob
import pandas as pd
from datetime import datetime
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL_NAME = "gpt-4o-mini"

# Load Data
print("Loading datasets...")
orders_df = pd.read_csv('data/olist_orders_dataset.csv')
items_df = pd.read_csv('data/olist_order_items_dataset.csv')
payments_df = pd.read_csv('data/olist_order_payments_dataset.csv')
sellers_df = pd.read_csv('data/olist_sellers_dataset.csv')
print("Datasets loaded.")

# Define schemas
class OrderSellerAssessment(BaseModel):
    is_canceled: bool
    is_unavailable: bool
    late_sellers: list[str] = Field(description="Seller IDs where order_delivered_carrier_date > shipping_limit_date")
    affected_items: list[str] = Field(description="Item IDs (format order_id:order_item_id)")

class DeliveryAssessment(BaseModel):
    is_delivered_after_estimate: bool
    carrier_received_after_limit: bool

class PaymentAssessment(BaseModel):
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    is_valid_split_payment: bool
    affected_payment_ids: list[str] = Field(description="Format order_id:payment_sequential")

class RootCause(BaseModel):
    cause_code: str
    rank: int

class ResponsibleParty(BaseModel):
    party_type: str
    party_id: str

class PolicyAssessment(BaseModel):
    primary_issue: str
    case_status: str
    confidence: float
    affected_order_ids: list[str]
    affected_item_ids: list[str]
    affected_seller_ids: list[str]
    affected_payment_ids: list[str]
    ranked_causes: list[RootCause]
    responsible_parties: list[ResponsibleParty]
    evidence_ids: list[str]
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    recommended_refund_brl: float
    resolution_actions: list[str]

# Agents
def order_seller_agent(order_data: dict, items_data: list[dict]) -> OrderSellerAssessment:
    prompt = f"""
    Analyze the order and items to determine status and late sellers.
    Order data: {json.dumps(order_data, default=str)}
    Items data: {json.dumps(items_data, default=str)}
    
    A seller is late if order_delivered_carrier_date > shipping_limit_date.
    Output JSON exactly matching the schema.
    """
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=OrderSellerAssessment,
    )
    return response.choices[0].message.parsed

def delivery_agent(order_data: dict, items_data: list[dict]) -> DeliveryAssessment:
    prompt = f"""
    Analyze delivery dates.
    Order data: {json.dumps(order_data, default=str)}
    Items data: {json.dumps(items_data, default=str)}
    
    is_delivered_after_estimate: order_delivered_customer_date > order_estimated_delivery_date.
    carrier_received_after_limit: order_delivered_carrier_date > shipping_limit_date of any item.
    """
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=DeliveryAssessment,
    )
    return response.choices[0].message.parsed

def payment_agent(payments_data: list[dict], items_data: list[dict]) -> PaymentAssessment:
    prompt = f"""
    Analyze payments and items for financial totals.
    Payments data: {json.dumps(payments_data, default=str)}
    Items data: {json.dumps(items_data, default=str)}
    
    item_total_brl: sum of 'price'
    freight_total_brl: sum of 'freight_value'
    payment_total_brl: sum of 'payment_value'
    is_valid_split_payment: True if >= 2 payment rows AND payment_total_brl matches (item_total_brl + freight_total_brl) within 0.10.
    """
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=PaymentAssessment,
    )
    return response.choices[0].message.parsed

def policy_agent(os_res: OrderSellerAssessment, d_res: DeliveryAssessment, p_res: PaymentAssessment, order_id: str) -> PolicyAssessment:
    prompt = f"""
    Apply EC_POLICY_V1 to determine the final assessment for order {order_id}.
    Inputs:
    Order/Seller: {os_res.model_dump_json()}
    Delivery: {d_res.model_dump_json()}
    Payment: {p_res.model_dump_json()}
    
    Rules Priority:
    1. canceled_order_paid: is_canceled and payment_total_brl > 0
       Party: platform / OLIST_PLATFORM. Refund: payment_total_brl. Action: issue_full_refund. Cause: ORDER_CANCELED_AFTER_PAYMENT
    2. unavailable_order_paid: is_unavailable and payment_total_brl > 0
       Party: platform / OLIST_PLATFORM. Refund: payment_total_brl. Action: issue_full_refund. Cause: ORDER_UNAVAILABLE_AFTER_PAYMENT
    3. late_delivery_seller: is_delivered_after_estimate and late_sellers is not empty
       Party: seller / <seller_id> from late_sellers. Refund: freight_total_brl. Action: refund_freight. Cause: SELLER_HANDOFF_AFTER_LIMIT
    4. late_delivery_logistics: is_delivered_after_estimate and late_sellers is empty
       Party: logistics_provider / LOGISTICS_PROVIDER. Refund: freight_total_brl. Action: refund_freight. Cause: CARRIER_DELIVERED_AFTER_ESTIMATE
    5. valid_split_payment: is_valid_split_payment == True
       Party: None. Refund: 0. Action: explain_valid_split_payment. Cause: MULTIPLE_PAYMENTS_RECONCILED
    6. unsupported_late_claim: NOT is_delivered_after_estimate
       Party: None. Refund: 0. Action: reject_late_refund. Cause: DELIVERY_WITHIN_ESTIMATE
       
    case_status: "action_required" if refund > 0 else "no_action".
    confidence: a float between 0.9 and 0.99.
    evidence_ids: List of valid evidence IDs formatted like:
    order:<order_id>
    item:<order_id>:<order_item_id>
    payment:<order_id>:<payment_sequential>
    seller:<seller_id>
    policy:<root_cause_code>
    """
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=PolicyAssessment,
    )
    return response.choices[0].message.parsed

def verifier_agent(case_id: str, assessment: PolicyAssessment) -> dict:
    out = assessment.model_dump()
    
    # Enforce limits
    def limit(l, n): return l[:n] if isinstance(l, list) else l
    
    res = {
        "case_id": case_id,
        "assessment": {
            "primary_issue": out["primary_issue"],
            "case_status": out["case_status"],
            "confidence": round(out["confidence"], 2)
        },
        "affected_entities": {
            "order_ids": limit(out["affected_order_ids"], 5),
            "item_ids": limit(out["affected_item_ids"], 5),
            "seller_ids": limit(out["affected_seller_ids"], 5),
            "payment_ids": limit(out["affected_payment_ids"], 5)
        },
        "root_cause_analysis": {
            "ranked_causes": limit(out["ranked_causes"], 3),
            "responsible_parties": limit(out["responsible_parties"], 3)
        },
        "evidence_ids": limit(out["evidence_ids"], 10),
        "financial_resolution": {
            "currency": "BRL",
            "item_total_brl": round(out["item_total_brl"], 2),
            "freight_total_brl": round(out["freight_total_brl"], 2),
            "payment_total_brl": round(out["payment_total_brl"], 2),
            "recommended_refund_brl": round(out["recommended_refund_brl"], 2)
        },
        "resolution_actions": limit(out["resolution_actions"], 5)
    }
    
    if not res["affected_entities"]["item_ids"]:
        res["financial_resolution"]["item_total_brl"] = 0.0
        res["financial_resolution"]["freight_total_brl"] = 0.0
        
    return res

trace_log = []

def process_case(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        claim = json.load(f)
    
    case_id = claim['case_id']
    order_id = claim['customer_request']['claimed_order_id']
    
    # Data Fetching
    o_row = orders_df[orders_df['order_id'] == order_id]
    i_rows = items_df[items_df['order_id'] == order_id]
    p_rows = payments_df[payments_df['order_id'] == order_id]
    
    order_data = o_row.to_dict(orient='records')[0] if not o_row.empty else {}
    items_data = i_rows.to_dict(orient='records')
    payments_data = p_rows.to_dict(orient='records')
    
    # Orchestrate Agents
    os_res = order_seller_agent(order_data, items_data)
    d_res = delivery_agent(order_data, items_data)
    p_res = payment_agent(payments_data, items_data)
    pol_res = policy_agent(os_res, d_res, p_res, order_id)
    final_output = verifier_agent(case_id, pol_res)
    
    # Trace
    trace_log.append({
        "case_id": case_id,
        "order_seller_agent": os_res.model_dump(),
        "delivery_agent": d_res.model_dump(),
        "payment_agent": p_res.model_dump(),
        "policy_agent": pol_res.model_dump(),
        "final_output": final_output
    })
    
    # Save
    os.makedirs('output', exist_ok=True)
    with open(f'output/{case_id}.json', 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    input_files = glob.glob('input/EC_*.json')
    for fpath in tqdm(input_files, desc="Processing cases"):
        try:
            process_case(fpath)
        except Exception as e:
            print(f"Error on {fpath}: {e}")
            
    with open('trace.jsonl', 'w', encoding='utf-8') as f:
        for t in trace_log:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
    
    # Metadata
    metadata = {
        "model": MODEL_NAME,
        "parameter_size": "8B",
        "framework": "OpenAI Python SDK (Structured Outputs)",
        "runtime": "Python 3"
    }
    with open('metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print("Done!")
