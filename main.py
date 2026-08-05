import os
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL_NAME = "gpt-4o-mini"

# ==============================================================================
# 1. DATA LOADER 
# ==============================================================================
print("Loading datasets...")
orders_df = pd.read_csv('data/olist_orders_dataset.csv')
items_df = pd.read_csv('data/olist_order_items_dataset.csv')
payments_df = pd.read_csv('data/olist_order_payments_dataset.csv')
sellers_df = pd.read_csv('data/olist_sellers_dataset.csv')
print("Datasets loaded.")

def parse_json_safely(text: str) -> dict:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())

# ==============================================================================
# 2. AGENT DEFINITIONS
# ==============================================================================

def order_agent(facts: str) -> dict:
    prompt = f"""You are the Order & Delivery Analysis Agent.
Analyze the following facts extracted from the database for an order.
Based on the dates and status, output a JSON object exactly matching this format (no extra text):
{{
  "is_canceled": true/false,
  "is_unavailable": true/false,
  "is_delivered_late": true/false (true if customer delivered date > estimated date),
  "seller_shipped_late": true/false (true if ANY item's carrier delivered date > its shipping limit date),
  "late_seller_ids": ["seller_id_1"],
  "late_item_ids": ["order_id:order_item_id"]
}}

Facts:
{facts}

Note:
- If a date is missing/NaN, it means the event hasn't happened.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return parse_json_safely(response.choices[0].message.content)

def payment_agent(facts: str) -> dict:
    prompt = f"""You are the Payment Analysis Agent.
Analyze the following facts extracted from the database for an order's payments.
Output a JSON object exactly matching this format (no extra text):
{{
  "total_payment": float,
  "total_order_cost": float,
  "is_valid_split_payment": true/false,
  "affected_payment_ids": ["order_id:payment_sequential"]
}}

Facts:
{facts}

A split payment is considered "valid" ONLY IF there are 2 or more payment records AND the total payment amount matches the total order cost (items + freight) within a 0.10 margin.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return parse_json_safely(response.choices[0].message.content)

def policy_agent(customer_msg: str, order_analysis: dict, payment_analysis: dict, order_id: str, totals: dict) -> dict:
    rulebook = """
# QUY ĐỊNH XỬ LÝ KHIẾU NẠI (EC_POLICY_V1)
Hệ thống ưu tiên dữ liệu kiểm chứng thay vì lời khiếu nại. Áp dụng theo thứ tự ưu tiên dưới đây:

1. canceled_order_paid: (Đơn hủy VÀ đã thanh toán > 0)
- Root Cause: ORDER_CANCELED_AFTER_PAYMENT
- Trách nhiệm: platform (OLIST_PLATFORM)
- Hành động: issue_full_refund (Hoàn tổng payment)

2. unavailable_order_paid: (Đơn không có sẵn VÀ đã thanh toán > 0)
- Root Cause: ORDER_UNAVAILABLE_AFTER_PAYMENT
- Trách nhiệm: platform (OLIST_PLATFORM)
- Hành động: issue_full_refund (Hoàn tổng payment)

3. late_delivery_seller: (Giao khách trễ VÀ Seller bàn giao cho carrier trễ)
- Root Cause: SELLER_HANDOFF_AFTER_LIMIT
- Trách nhiệm: seller (Mã seller vi phạm)
- Hành động: refund_freight (Hoàn phí vận chuyển của các item bị trễ)

4. late_delivery_logistics: (Giao khách trễ VÀ Seller KHÔNG bàn giao trễ)
- Root Cause: CARRIER_DELIVERED_AFTER_ESTIMATE
- Trách nhiệm: logistics_provider (LOGISTICS_PROVIDER)
- Hành động: refund_freight (Hoàn tổng freight của đơn)

5. valid_split_payment: (Khách thanh toán >=2 payments, tổng payment khớp tổng chi phí)
- Root Cause: MULTIPLE_PAYMENTS_RECONCILED
- Trách nhiệm: system (Không hoàn tiền)
- Hành động: explain_valid_split_payment

6. unsupported_late_claim: (Không trễ, không lỗi thanh toán)
- Root Cause: DELIVERY_WITHIN_ESTIMATE
- Trách nhiệm: customer (Không hoàn tiền)
- Hành động: reject_late_refund
"""
    
    prompt = f"""You are the Master Policy Agent.
Resolve a customer's request using strictly the EC_POLICY_V1 rulebook.

CUSTOMER REQUEST: "{customer_msg}"
ORDER_ID: {order_id}

ORDER AGENT CONCLUSIONS:
- Canceled: {order_analysis.get('is_canceled')}
- Unavailable: {order_analysis.get('is_unavailable')}
- Delivered Late: {order_analysis.get('is_delivered_late')}
- Seller Shipped Late: {order_analysis.get('seller_shipped_late')}
- Late Sellers: {order_analysis.get('late_seller_ids')}
- Late Items: {order_analysis.get('late_item_ids')}

PAYMENT AGENT CONCLUSIONS:
- Total Payment: {payment_analysis.get('total_payment')}
- Is Valid Split Payment: {payment_analysis.get('is_valid_split_payment')}
- Affected Payment IDs: {payment_analysis.get('affected_payment_ids')}

FINANCIALS:
- Item Total: {totals['item_total']}
- Freight Total: {totals['freight_total']}
- Late Items Freight: {totals['late_freight']}
- Payment Total: {totals['payment_total']}

Determine the final resolution and output ONLY a JSON object exactly matching this schema:
{{
  "assessment": {{
    "primary_issue": "one of: canceled_order_paid, unavailable_order_paid, late_delivery_seller, late_delivery_logistics, valid_split_payment, unsupported_late_claim",
    "case_status": "action_required or no_action",
    "confidence": 0.95
  }},
  "affected_entities": {{
    "order_ids": ["{order_id}"],
    "item_ids": ["order_id:order_item_id", ...],
    "seller_ids": ["seller_id_1", ...],
    "payment_ids": ["order_id:payment_sequential", ...]
  }},
  "root_cause_analysis": {{
    "ranked_causes": [
      {{ "cause_code": "Root cause code from policy", "rank": 1 }}
    ],
    "responsible_parties": [
      {{ "party_type": "seller/platform/logistics_provider/system/customer", "party_id": "ID or constant like OLIST_PLATFORM" }}
    ]
  }},
  "evidence_ids": [
    "order:{order_id}",
    "item:<order_id>:<item_id>",
    "payment:<order_id>:<seq>",
    "seller:<seller_id>",
    "policy:<cause_code>"
  ],
  "financial_resolution": {{
    "currency": "BRL",
    "item_total_brl": {totals['item_total']},
    "freight_total_brl": {totals['freight_total']},
    "payment_total_brl": {totals['payment_total']},
    "recommended_refund_brl": float (calculate based on policy)
  }},
  "resolution_actions": ["action_code_from_policy"]
}}
Note for evidence_ids: format must exactly match: `order:<order_id>`, `item:<order_id>:<item_id>`, `payment:<order_id>:<seq>`, `seller:<seller_id>`, `policy:<cause_code>`. Max 10 items.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return parse_json_safely(response.choices[0].message.content)

# ==============================================================================
# 4. ORCHESTRATOR PIPELINE
# ==============================================================================

def process_case(case_json: dict) -> dict:
    req = case_json['customer_request']
    order_id = req['claimed_order_id']
    msg = req['message']
    
    o_row = orders_df[orders_df['order_id'] == order_id]
    i_rows = items_df[items_df['order_id'] == order_id]
    p_rows = payments_df[payments_df['order_id'] == order_id]
    
    order_status = o_row['order_status'].iloc[0] if not o_row.empty else "unknown"
    est_date = o_row['order_estimated_delivery_date'].iloc[0] if not o_row.empty else "NaN"
    cust_date = o_row['order_delivered_customer_date'].iloc[0] if not o_row.empty else "NaN"
    carr_date = o_row['order_delivered_carrier_date'].iloc[0] if not o_row.empty else "NaN"
    
    order_facts = f"- Order Status: {order_status}\n"
    order_facts += f"- Order Estimated Delivery Date: {est_date}\n"
    order_facts += f"- Order Delivered to Customer Date: {cust_date}\n"
    order_facts += f"- Order Delivered to Carrier Date: {carr_date}\n\n"
    order_facts += "- Items Details:\n"
    
    late_freight_sum = 0.0
    for _, row in i_rows.iterrows():
        order_facts += f"  * Item {row['order_id']}:{row['order_item_id']} | Seller: {row['seller_id']} | Shipping Limit Date: {row['shipping_limit_date']}\n"
        # Pre-calculate late freight
        s_limit = str(row['shipping_limit_date'])
        if s_limit != "nan" and str(carr_date) != "nan" and str(carr_date) != "NaN":
            if carr_date > s_limit:
                late_freight_sum += float(row['freight_value'])
    
    payment_facts = "- Payment Details:\n"
    for _, row in p_rows.iterrows():
        payment_facts += f"  * Payment ID: {row['order_id']}:{row['payment_sequential']} | Amount: {row['payment_value']}\n"
    
    total_items = float(i_rows['price'].sum()) if not i_rows.empty else 0.0
    total_freight = float(i_rows['freight_value'].sum()) if not i_rows.empty else 0.0
    total_payment = float(p_rows['payment_value'].sum()) if not p_rows.empty else 0.0
    
    payment_facts += f"\n- Total Items Price: {total_items}\n"
    payment_facts += f"- Total Freight Value: {total_freight}\n"
    payment_facts += f"- Sum of Item + Freight: {total_items + total_freight}\n"

    order_analysis = order_agent(order_facts)
    payment_analysis = payment_agent(payment_facts)
    
    totals = {
        "item_total": round(total_items, 2),
        "freight_total": round(total_freight, 2),
        "late_freight": round(late_freight_sum, 2),
        "payment_total": round(total_payment, 2)
    }
    
    final_decision = policy_agent(msg, order_analysis, payment_analysis, order_id, totals)
    
    # Enforce constraints
    if "evidence_ids" in final_decision:
        final_decision["evidence_ids"] = final_decision["evidence_ids"][:10]
    
    result = {
        "case_id": case_json['case_id']
    }
    result.update(final_decision)
    
    # Handle missing items corner case for financial resolution
    if "financial_resolution" in result:
        result["financial_resolution"]["item_total_brl"] = totals["item_total"]
        result["financial_resolution"]["freight_total_brl"] = totals["freight_total"]
        result["financial_resolution"]["payment_total_brl"] = totals["payment_total"]
        
        # Round the recommended refund
        if "recommended_refund_brl" in result["financial_resolution"]:
            result["financial_resolution"]["recommended_refund_brl"] = round(float(result["financial_resolution"]["recommended_refund_brl"]), 2)
            
    if "affected_entities" in result:
        if totals["item_total"] == 0.0:
            result["affected_entities"]["item_ids"] = []
            result["affected_entities"]["seller_ids"] = []

    return result

def main():
    import glob
    input_files = glob.glob('input/EC_*.json')
    input_files.sort()
    
    os.makedirs('output', exist_ok=True)
    
    trace_log = []
    
    for file_path in tqdm(input_files, desc="Processing cases"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                case_data = json.load(f)
                
            result = process_case(case_data)
            
            filename = os.path.basename(file_path)
            with open(f"output/{filename}", 'w', encoding='utf-8') as out_f:
                json.dump(result, out_f, indent=2, ensure_ascii=False)
                
            trace_log.append({
                "claim_id": result.get("case_id", "Unknown"),
                "status": "success",
                "issue": result.get("assessment", {}).get("primary_issue", "Unknown")
            })
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            trace_log.append({"file": file_path, "status": "error", "error": str(e)})

    with open('trace.jsonl', 'w') as f:
        for trace in trace_log:
            f.write(json.dumps(trace) + '\n')
            
    with open('metadata.json', 'w') as f:
        json.dump({
            "student_id": "01903",
            "model_used": MODEL_NAME,
            "architecture": "Multi-Agent with OpenRouter API"
        }, f, indent=2)
        
    print("Done!")

if __name__ == '__main__':
    main()
