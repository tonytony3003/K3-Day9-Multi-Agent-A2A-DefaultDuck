# Multi-Agent Architecture Specification — E-commerce Dispute Resolution

Hệ thống được thiết kế theo kiến trúc **Multi-Agent Handoff Workflow** nhằm xử lý tự động các khiếu nại thương mại điện tử trên dữ liệu Olist theo bộ quy tắc nghiệp vụ `EC_POLICY_V1`.

---

## 1. Sơ đồ hệ thống Agent (Agent Diagram)

                   ┌─────────────────────────┐
                   │    Coordinator Agent    │
                   └────────────┬────────────┘
                                │ (Input Case Ticket)
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐
│   Order & Seller   │    │   Payment Agent    │    │   Delivery Agent   │
│       Agent        │    │                    │    │                    │
└──────────┬─────────┘    └─────────┬──────────┘    └─────────┬──────────┘
│                        │                         │
└────────────────────────┼─────────────────────────┘
│ (Domain Evidence Payload)
▼
┌─────────────────────────┐
│      Policy Agent       │ (EC_POLICY_V1 Engine)
└────────────┬────────────┘
│ (Draft Resolution)
▼
┌─────────────────────────┐
│     Verifier Agent      │ (Schema & Limit Validation)
└────────────┬────────────┘
│
▼
[output/EC_xxx.json & trace.jsonl]


---

## 2. Vai trò và Quyền truy cập dữ liệu (Roles & Access Permissions)

| Agent Name | Vai trò chính (Role) | Thao tác | Quyền truy cập dữ liệu (Data Access) |
| :--- | :--- | :--- | :--- |
| **Coordinator Agent** | Tiếp nhận case khiếu nại từ `input/`, phân trích `claimed_order_id` và điều phối luồng xử lý. | Read / Write | `input/*.json`, `trace.jsonl` |
| **Order & Seller Agent** | Truy xuất đơn hàng, danh sách items, xác định người bán (`seller_id`) và kiểm tra hạn bàn giao (`shipping_limit_date`). | Read-only | `data/olist_orders_dataset.csv`<br>`data/olist_order_items_dataset.csv`<br>`data/olist_sellers_dataset.csv` |
| **Payment Agent** | Trích xuất các giao dịch thanh toán, kiểm tra giao dịch tách dòng (`split payment`) và đối soát tổng tiền. | Read-only | `data/olist_order_payments_dataset.csv` |
| **Delivery Agent** | So sánh thời gian giao thực tế (`order_delivered_customer_date`) và ngày hẹn giao (`order_estimated_delivery_date`). | Read-only | `data/olist_orders_dataset.csv` |
| **Policy Agent** | Nhận dữ liệu tổng hợp, áp dụng quy tắc ưu tiên `EC_POLICY_V1` để đưa ra kết luận, bên chịu trách nhiệm và khoản hoàn trả. | Read-only | In-memory payload từ các domain agents |
| **Verifier Agent** | Thẩm định định dạng Evidence ID, áp giới hạn số lượng phần tử, kiểm tra định dạng JSON và ghi file kết quả. | Read / Write | `output/*.json`, `trace.jsonl` |

---

## 3. Luồng Chuyển Giao Công Việc (Handoff Workflow)

1. **Khởi tạo (Initialization Phase)**:
   * **Coordinator Agent** đọc file input `input/EC_xxx.json`, lấy `claimed_order_id` và kích hoạt luồng xử lý đồng thời khởi tạo nhật ký vết tại `trace.jsonl`.

2. **Thu thập dữ liệu chuyên miền (Domain Data Extraction Phase)**:
   * **Order & Seller Agent** lấy thông tin trạng thái đơn, danh sách mặt hàng, tính `item_total` và `freight_total`. So sánh `order_delivered_carrier_date` với `shipping_limit_date` của từng item để phát hiện seller vi phạm.
   * **Payment Agent** gom tất cả dòng payment của order, tính `payment_total` và xác định trạng thái thanh toán nhiều dòng (split payment).
   * **Delivery Agent** xác định đơn hàng có bị giao trễ hay không bằng việc đối sánh `order_delivered_customer_date` > `order_estimated_delivery_date`.

3. **Ra quyết định nghiệp vụ (Policy Evaluation Phase)**:
   * Các Domain Agents thực hiện handoff toàn bộ bằng chứng số liệu sang **Policy Agent**.
   * **Policy Agent** đánh giá các điều kiện theo **thứ tự ưu tiên nghiêm ngặt** của `EC_POLICY_V1`:
     1. `canceled_order_paid`
     2. `unavailable_order_paid`
     3. `late_delivery_seller`
     4. `late_delivery_logistics`
     5. `valid_split_payment`
     6. `unsupported_late_claim`

4. **Kiểm tra & Xuất kết quả (Validation & Export Phase)**:
   * **Policy Agent** bàn giao bản thảo quyết định cho **Verifier Agent**.
   * **Verifier Agent** thực hiện các bước kiểm duyệt cuối:
     * Dựng danh sách **Evidence ID** chính xác theo chuẩn (`order:<id>`, `item:<id>:<seq>`, `payment:<id>:<seq>`, `seller:<id>`, `policy:<code>`).
     * Áp giới hạn kỹ thuật: Tối đa 5 IDs cho mỗi entity list, tối đa 10 evidence IDs, 3 root causes, 3 responsible parties và 5 actions.
     * Làm tròn tiền tệ 2 chữ số thập phân (`BRL`).
     * Ghi file `output/EC_xxx.json` và append log bước chạy vào `trace.jsonl`.