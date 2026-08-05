# Architecture - Multi-Agent E-commerce Dispute Resolution

## Tổng quan hệ thống

Hệ thống gồm **6 Agent** được điều phối tuần tự bởi `CoordinatorAgent`. Mỗi agent có trách nhiệm đơn lẻ (Single Responsibility), nhận dữ liệu qua **handoff** từ agent trước và trả kết quả có cấu trúc cho agent tiếp theo.

## Sơ đồ kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                          │
│              input/EC_001.json ... EC_050.json              │
└───────────────────────────┬─────────────────────────────────┘
                            │ case_input (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CoordinatorAgent                          │
│  - Nhận case input                                          │
│  - Gọi tuần tự các sub-agent                               │
│  - Tổng hợp output JSON theo schema                         │
│  - Ghi file output + trace                                  │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
 Step 1     Step 2     Step 3     Step 4     Step 5
   │          │          │          │          │
┌──┴──┐    ┌──┴──┐    ┌──┴──┐    ┌──┴──┐    ┌──┴──┐
│Order│    │Pay- │    │Deli-│    │Pol- │    │Veri-│
│Seller    │ment │    │very │    │icy  │    │fier │
│Agent│    │Agent│    │Agent│    │Agent│    │Agent│
└──┬──┘    └──┬──┘    └──┬──┘    └──┬──┘    └──┬──┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
order_data payment_data delivery  policy    validated
              data       _data     _data     output
```

## Chi tiết từng Agent

### 1. DataLoader (Shared Resource)
- **Vai trò**: Load toàn bộ 9 file CSV Olist vào bộ nhớ khi khởi động
- **Quyền truy cập**: Toàn bộ file trong `data/`
- **Output**: Pandas DataFrames, query helpers theo `order_id`
- **Pattern**: Singleton, được inject vào tất cả agents cần đọc dữ liệu

### 2. CoordinatorAgent
- **Vai trò**: Điều phối pipeline, tổng hợp output cuối
- **Quyền truy cập**: Tất cả sub-agents
- **Input**: `case_input` (dict từ JSON file)
- **Output**: `(output_json, trace_record)`
- **Handoff**: Gọi từng agent theo thứ tự, truyền output của agent trước làm input cho agent sau

### 3. OrderSellerAgent
- **Vai trò**: Truy vấn thông tin đơn hàng, item, seller
- **Quyền truy cập**: `orders`, `order_items`, `sellers` tables
- **Input**: `order_id`
- **Output**:
  - `order_status`, timestamps
  - Danh sách `items` (price, freight, shipping_limit_date)
  - `seller_ids`, `item_total_brl`, `freight_total_brl`
  - `late_seller_handoff` (bool): carrier nhận hàng sau `shipping_limit_date`
  - `late_seller_ids`: danh sách seller vi phạm hạn bàn giao

### 4. PaymentAgent
- **Vai trò**: Phân tích thanh toán, đối soát với giá trị đơn hàng
- **Quyền truy cập**: `order_payments` table
- **Input**: `order_id`, `item_total_brl`, `freight_total_brl`
- **Output**:
  - Danh sách `payments`, `payment_total_brl`
  - `is_split_payment` (bool): có ≥ 2 payment rows
  - `payment_matches_order` (bool): tổng payment khớp item+freight trong ±0.10 BRL

### 5. DeliveryAgent
- **Vai trò**: Phân tích timing giao hàng
- **Quyền truy cập**: Dữ liệu từ `OrderSellerAgent` (không query CSV trực tiếp)
- **Input**: `order_data` từ OrderSellerAgent
- **Output**:
  - `late_delivery_to_customer` (bool): giao sau `order_estimated_delivery_date`
  - `delivered_to_customer` (bool)
  - Các timestamp để trace

### 6. PolicyAgent
- **Vai trò**: Áp dụng EC_POLICY_V1, quyết định kết quả
- **Quyền truy cập**: Chỉ nhận output từ 3 agents trước (không query CSV)
- **Input**: `order_data`, `payment_data`, `delivery_data`
- **Luồng quyết định** (theo thứ tự ưu tiên):
  1. `canceled_order_paid` → hoàn toàn bộ payment
  2. `unavailable_order_paid` → hoàn toàn bộ payment
  3. `late_delivery_seller` → hoàn freight (seller bàn giao muộn)
  4. `late_delivery_logistics` → hoàn freight (vận chuyển giao muộn)
  5. `valid_split_payment` → không hoàn, giải thích
  6. `unsupported_late_claim` → từ chối claim
- **Output**: `primary_issue`, `responsible_parties`, `recommended_refund_brl`, `resolution_actions`

### 7. VerifierAgent
- **Vai trò**: Kiểm tra và fix output trước khi ghi file
- **Quyền truy cập**: Output JSON từ bước assembly
- **Kiểm tra**:
  - Schema compliance (primary_issue, case_status valid values)
  - Evidence ID format (regex validation)
  - Array limits: max 5 entity IDs, max 10 evidence IDs, max 3 root causes, max 3 responsible parties, max 5 actions
  - Clamp confidence trong [0, 1]
  - Round số tiền về 2 chữ số thập phân

## Luồng Handoff

```
CoordinatorAgent
    │
    ├─► OrderSellerAgent(order_id)
    │       └─► order_data {status, items, freight_total, late_seller_handoff, ...}
    │
    ├─► PaymentAgent(order_id, item_total, freight_total)
    │       └─► payment_data {payment_total, is_split_payment, payment_matches, ...}
    │
    ├─► DeliveryAgent(order_data)
    │       └─► delivery_data {late_delivery_to_customer, ...}
    │
    ├─► PolicyAgent(order_data, payment_data, delivery_data)
    │       └─► policy_data {primary_issue, refund, actions, ...}
    │
    ├─► [assemble output JSON]
    │
    └─► VerifierAgent(output)
            └─► validated_output → ghi file
```

## Quyền truy cập dữ liệu

| Agent | orders | order_items | order_payments | sellers | Agents khác |
|-------|--------|-------------|----------------|---------|-------------|
| DataLoader | ✓ | ✓ | ✓ | ✓ | - |
| OrderSellerAgent | ✓ | ✓ | - | ✓ | DataLoader |
| PaymentAgent | - | - | ✓ | - | DataLoader |
| DeliveryAgent | - | - | - | - | order_data |
| PolicyAgent | - | - | - | - | 3 agent outputs |
| VerifierAgent | - | - | - | - | assembled output |

## Output

- **`output/EC_XXX.json`**: Kết quả xử lý từng case theo schema bắt buộc
- **`trace.jsonl`**: Log trace từng bước xử lý của 50 case (1 dòng JSON/case)
