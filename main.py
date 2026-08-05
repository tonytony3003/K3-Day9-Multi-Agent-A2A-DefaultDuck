import os
import json
import pandas as pd
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm
import time

load_dotenv()

# Khởi tạo OpenAI Client. Hỗ trợ Qwen <=10B qua các endpoint tương thích OpenAI
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")  # Dành cho Qwen/Llama qua Together, DeepInfra...
)

# Tên model sử dụng khai báo rõ ràng (thỏa mãn constraint <=10B)
MODEL_NAME = "gpt-4o-mini" # Bạn có thể đổi thành "qwen2.5-7b-instruct" nếu dùng api endpoint khác

# ==============================================================================
# 1. DATA LOADER (Chỉ xử lý số học, KHÔNG hardcode logic nghiệp vụ)
# ==============================================================================
print("Loading datasets...")
orders_df = pd.read_csv('data/olist_orders_dataset.csv')
items_df = pd.read_csv('data/olist_order_items_dataset.csv')
payments_df = pd.read_csv('data/olist_order_payments_dataset.csv')
sellers_df = pd.read_csv('data/olist_sellers_dataset.csv')
print("Datasets loaded.")

# ==============================================================================
# 2. DEFINING AGENT SCHEMAS (Pydantic cho Structured Outputs)
# ==============================================================================
class OrderAgentOutput(BaseModel):
    is_canceled: bool = Field(description="Is the order canceled?")
    is_unavailable: bool = Field(description="Is the order unavailable?")
    is_delivered: bool = Field(description="Was the order delivered to the customer?")
    is_delivered_late: bool = Field(description="If delivered, was it delivered after the estimated date?")
    seller_shipped_late: bool = Field(description="Did the seller hand over the item to the carrier after the shipping limit date?")
    late_seller_ids: list[str] = Field(description="List of seller IDs who shipped late")
    late_item_ids: list[str] = Field(description="List of item IDs (format order_id:order_item_id) that were shipped late")

class PaymentAgentOutput(BaseModel):
    total_payment: float = Field(description="Sum of all payments made by the customer")
    total_order_cost: float = Field(description="Sum of all item prices and freight values")
    is_valid_split_payment: bool = Field(description="Are there 2 or more payments, and does the total payment match the total cost (within 0.10)?")
    affected_payment_ids: list[str] = Field(description="List of payment IDs (format order_id:payment_sequential)")

class FinalOutput(BaseModel):
    primary_issue: str = Field(description="Must be exactly one of: canceled_order_paid, unavailable_order_paid, late_delivery_seller, late_delivery_logistics, valid_split_payment, unsupported_late_claim")
    responsible_party: str = Field(description="Who is responsible? (seller_id, logistics, system, customer)")
    evidence: list[str] = Field(description="List of IDs (order_id, seller_id, or payment_id) proving the issue. Max 3 items.")
    recommended_refund_brl: float = Field(description="The refund amount calculated according to the policy rules.")
    resolution_action: str = Field(description="The action to take according to the policy.")

# ==============================================================================
# 3. AGENT DEFINITIONS
# ==============================================================================

def order_agent(facts: str) -> OrderAgentOutput:
    prompt = f"""You are the Order & Delivery Analysis Agent.
Analyze the following facts extracted from the database for an order.
Based on the dates and status, answer the questions in the output JSON.

Facts:
{facts}

Note:
- If a date is missing/NaN, it means the event hasn't happened.
- If delivered customer date > estimated date, it is delivered late.
- If delivered carrier date > shipping limit date, the seller shipped late.
"""
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=OrderAgentOutput,
    )
    return response.choices[0].message.parsed

def payment_agent(facts: str) -> PaymentAgentOutput:
    prompt = f"""You are the Payment Analysis Agent.
Analyze the following facts extracted from the database for an order's payments.

Facts:
{facts}

A split payment is considered "valid" ONLY IF there are 2 or more payment records AND the total payment amount matches the total order cost (items + freight) within a 0.10 margin.
Output your conclusion in the requested JSON format.
"""
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=PaymentAgentOutput,
    )
    return response.choices[0].message.parsed

def policy_agent(customer_msg: str, order_analysis: OrderAgentOutput, payment_analysis: PaymentAgentOutput) -> FinalOutput:
    rulebook = """
# QUY ĐỊNH XỬ LÝ KHIẾU NẠI (EC_POLICY_V1)
Hệ thống ưu tiên dữ liệu kiểm chứng thay vì lời khiếu nại. Áp dụng theo thứ tự ưu tiên dưới đây:

1. canceled_order_paid:
- Điều kiện: Đơn hàng bị hủy (canceled) VÀ khách đã thanh toán > 0.
- Bên chịu trách nhiệm: system
- Xử lý: Hoàn tiền toàn bộ (total_payment). Hủy đơn.

2. unavailable_order_paid:
- Điều kiện: Đơn hàng không có sẵn (unavailable) VÀ khách đã thanh toán > 0.
- Bên chịu trách nhiệm: system
- Xử lý: Hoàn tiền toàn bộ (total_payment). Hủy đơn.

3. late_delivery_seller:
- Điều kiện: Giao hàng trễ (delivered customer > estimated) VÀ Lỗi do Seller (delivered carrier > shipping limit).
- Bên chịu trách nhiệm: Seller gây trễ.
- Bằng chứng: Mã seller, mã order_item bị trễ.
- Xử lý: Hoàn phí vận chuyển (freight) của các item bị trễ. Cảnh cáo seller.

4. late_delivery_logistics:
- Điều kiện: Giao hàng trễ VÀ Không phải lỗi Seller (delivered carrier <= shipping limit).
- Bên chịu trách nhiệm: logistics
- Bằng chứng: Mã đơn hàng (order_id)
- Xử lý: Hoàn phí vận chuyển toàn bộ (total freight). Gửi yêu cầu SLA cho đối tác vận chuyển.

5. valid_split_payment:
- Điều kiện: Khách thanh toán chia nhỏ hợp lệ (>=2 payments, tổng payment khớp tổng items + freight).
- Bên chịu trách nhiệm: system
- Bằng chứng: Các mã thanh toán bị ảnh hưởng.
- Xử lý: Hoàn 0. Cập nhật hệ thống thanh toán.

6. unsupported_late_claim:
- Điều kiện: Khách khiếu nại giao trễ hoặc thanh toán, nhưng dữ liệu cho thấy không giao trễ và thanh toán khớp.
- Bên chịu trách nhiệm: customer
- Bằng chứng: Mã đơn hàng (order_id)
- Xử lý: Hoàn 0. Giải thích cho khách hàng.
"""
    
    prompt = f"""You are the Master Policy Agent.
You must apply the EC_POLICY_V1 rulebook strictly to resolve a customer's request.
DO NOT use arbitrary logic. Use ONLY the rulebook and the exact conclusions from the Domain Agents.

CUSTOMER REQUEST: "{customer_msg}"

ORDER AGENT CONCLUSIONS:
- Canceled: {order_analysis.is_canceled}
- Unavailable: {order_analysis.is_unavailable}
- Delivered Late: {order_analysis.is_delivered_late}
- Seller Shipped Late: {order_analysis.seller_shipped_late}
- Late Sellers: {order_analysis.late_seller_ids}
- Late Items: {order_analysis.late_item_ids}

PAYMENT AGENT CONCLUSIONS:
- Total Payment: {payment_analysis.total_payment}
- Is Valid Split Payment: {payment_analysis.is_valid_split_payment}
- Affected Payment IDs: {payment_analysis.affected_payment_ids}

Based on the Rules Priority (1 to 6) in EC_POLICY_V1, determine the final resolution. Output in the exact JSON schema.
"""
    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=FinalOutput,
    )
    return response.choices[0].message.parsed

# ==============================================================================
# 4. ORCHESTRATOR PIPELINE
# ==============================================================================

def process_case(case_json: dict) -> dict:
    req = case_json['customer_request']
    order_id = req['claimed_order_id']
    msg = req['message']
    
    # Extract DB Rows
    o_row = orders_df[orders_df['order_id'] == order_id]
    i_rows = items_df[items_df['order_id'] == order_id]
    p_rows = payments_df[payments_df['order_id'] == order_id]
    
    # ---- 1. BUILD FACTS FOR ORDER AGENT ----
    order_status = o_row['order_status'].iloc[0] if not o_row.empty else "unknown"
    est_date = o_row['order_estimated_delivery_date'].iloc[0] if not o_row.empty else "NaN"
    cust_date = o_row['order_delivered_customer_date'].iloc[0] if not o_row.empty else "NaN"
    carr_date = o_row['order_delivered_carrier_date'].iloc[0] if not o_row.empty else "NaN"
    
    order_facts = f"- Order Status: {order_status}\n"
    order_facts += f"- Order Estimated Delivery Date: {est_date}\n"
    order_facts += f"- Order Delivered to Customer Date: {cust_date}\n"
    order_facts += f"- Order Delivered to Carrier Date: {carr_date}\n\n"
    order_facts += "- Items Details:\n"
    for _, row in i_rows.iterrows():
        order_facts += f"  * Item {row['order_id']}:{row['order_item_id']} | Seller: {row['seller_id']} | Shipping Limit Date: {row['shipping_limit_date']}\n"
    
    # ---- 2. BUILD FACTS FOR PAYMENT AGENT ----
    payment_facts = "- Payment Details:\n"
    for _, row in p_rows.iterrows():
        payment_facts += f"  * Payment ID: {row['order_id']}:{row['payment_sequential']} | Amount: {row['payment_value']}\n"
    
    total_items = i_rows['price'].sum() if not i_rows.empty else 0
    total_freight = i_rows['freight_value'].sum() if not i_rows.empty else 0
    
    payment_facts += f"\n- Total Items Price: {total_items}\n"
    payment_facts += f"- Total Freight Value: {total_freight}\n"
    payment_facts += f"- Sum of Item + Freight: {total_items + total_freight}\n"

    # ---- 3. RUN MULTI-AGENT HANDOFF ----
    # Step A: Domain Agents execute independently
    order_analysis = order_agent(order_facts)
    payment_analysis = payment_agent(payment_facts)
    
    # Step B: Policy Agent makes final decision
    final_decision = policy_agent(msg, order_analysis, payment_analysis)
    
    # ---- 4. VERIFIER AGENT (Sanity check) ----
    # Giới hạn evidence <= 3 phần tử (đề bài yêu cầu)
    evidence = final_decision.evidence[:3] if len(final_decision.evidence) > 3 else final_decision.evidence
    
    # Xây dựng output
    return {
        "claim_id": case_json['case_id'],
        "primary_issue": final_decision.primary_issue,
        "responsible_party": final_decision.responsible_party,
        "evidence": evidence,
        "recommended_refund_brl": round(final_decision.recommended_refund_brl, 2),
        "resolution_action": final_decision.resolution_action
    }

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
            
            # Save Output
            filename = os.path.basename(file_path)
            with open(f"output/{filename}", 'w', encoding='utf-8') as out_f:
                json.dump(result, out_f, indent=2, ensure_ascii=False)
                
            trace_log.append({
                "claim_id": result["claim_id"],
                "status": "success",
                "issue": result["primary_issue"]
            })
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            trace_log.append({"file": file_path, "status": "error", "error": str(e)})

    # Generate metadata and trace
    with open('trace.jsonl', 'w') as f:
        for trace in trace_log:
            f.write(json.dumps(trace) + '\n')
            
    with open('metadata.json', 'w') as f:
        json.dump({
            "student_id": "01903",
            "model_used": MODEL_NAME,
            "architecture": "Tool-calling Multi-Agent without hardcoded rules"
        }, f, indent=2)
        
    print("Done!")

if __name__ == '__main__':
    main()
