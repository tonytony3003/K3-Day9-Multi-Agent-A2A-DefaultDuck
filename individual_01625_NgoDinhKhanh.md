# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung |
| --------------- | ------------ |
| Họ và tên       | Ngô Đình Khánh |
| MSSV            | 2A202601625 |
| Khóa/Lớp        | K3 |
| Vai trò chính   | Full-stack Multi-Agent Architect & Developer |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Data Access Layer | `src/data_loader.py` | CSV Olist dataset | `OlistData` class dict O(1) lookup | Hoàn thành |
| LLM Integration Client | `src/llm_client.py` | Groq API Key & Prompts | JSON responses từ model `llama-3.1-8b-instant` | Hoàn thành |
| Multi-Agent Pipeline | `src/agents/*.py`, `src/main.py` | 50 Input JSON files | 50 Output JSON files + `trace.jsonl` | Hoàn thành |
| Architecture Doc | `architecture.md` | System design & Handoff flow | Mermaid Diagram & Documentation | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------------------- | ----------------------------- | ----------------------- |
| Debug API & Cloudflare headers | LLM Integration | Thêm User-Agent header khắc phục lỗi HTTP 403 |
| Verification & Schema Check | VerifierAgent | Đảm bảo 100% output tuân thủ schema đề bài |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Khởi tạo LLM Client | `src/llm_client.py` | Gọi Groq REST API thành công với model `llama-3.1-8b-instant` | `python src/test_llm.py` |
| Xây dựng 6 Agent A2A | `src/agents/` | 6 Agent chuyên biệt (Coordinator, Order, Delivery, Payment, Policy, Verifier) | `python src/main.py` |
| Sinh 50 file Output JSON | `output/EC_001.json` - `EC_050.json` | 50 file kết quả chuẩn hóa đúng schema | Check file trong `output/` |
| Sinh audit log | `logging/trace.jsonl`, `logging/metadata.json` | 300 trace entries ghi nhận luồng chạy thật | Inspect `trace.jsonl` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Tự động điều tra và giải quyết 50 khiếu nại thương mại điện tử dựa trên dữ liệu thật của Olist bằng kiến trúc Multi-Agent phối hợp, sử dụng model AI ≤ 10B parameters.

### Cách triển khai

1. **Data Layer (`data_loader.py`):** Đọc dữ liệu CSV vào bộ nhớ bằng Python `csv.DictReader` cho phép truy vấn O(1) theo `order_id`.
2. **LLM Client Layer (`llm_client.py`):** Viết client kết nối Groq API gọi model `llama-3.1-8b-instant` (8B parameters, đáp ứng tiêu chí ≤ 10B), cấu hình rate-limiting và auto-retry.
3. **Multi-Agent Orchestration:**
   - **OrderAgent:** Lấy thông tin đơn hàng, items, seller và dùng LLM tóm tắt trạng thái.
   - **DeliveryAgent:** Dùng LLM so sánh timestamp giao hàng thực tế vs ước tính và hạn bàn giao seller.
   - **PaymentAgent:** Dùng LLM đối soát tổng tiền thanh toán với (giá item + phí vận chuyển).
   - **PolicyAgent:** Dùng LLM áp dụng bộ quy tắc `EC_POLICY_V1` theo đúng thứ tự ưu tiên 1-6.
   - **VerifierAgent:** Dùng LLM validate output JSON, định dạng bằng chứng (evidence IDs) và làm tròn số tiền.
   - **CoordinatorAgent:** Điều phối luồng handoff giữa các agent và ghi nhật ký `trace.jsonl`.

### Input, output và contract

| Thành phần | Mô tả |
| ----------------------- | -------------------------------------- |
| Input | `input/EC_001.json` .. `EC_050.json` |
| Output | `output/EC_001.json` .. `EC_050.json` |
| Module phụ thuộc | `urllib.request`, `json`, `csv` (pure Python stdlib) |
| Module sử dụng output | Hệ thống chấm điểm tự động |
| Điều kiện lỗi cần xử lý | Rate limit (HTTP 429), Cloudflare header (HTTP 403), JSON parsing fallback |

### Cách xác minh

```bash
python src/main.py
```

- **Kết quả mong đợi:** Xử lý thành công 50/50 cases, sinh 50 file trong `output/`, `trace.jsonl` chứa 300 entries, `metadata.json` khai báo đúng model `llama-3.1-8b-instant`.
- **Kết quả thực tế:** Xử lý thành công 50/50 cases.
- **Artifact/log:** `logging/trace.jsonl`, `logging/metadata.json`, `architecture.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn mô hình AI dưới 10B parameters, chạy ổn định, nhanh và hỗ trợ JSON mode qua API.
- **Các phương án đã cân nhắc:**
  1. Local Ollama (tốn tài nguyên máy, tốc độ chậm khi chạy 50 cases × 5 agents).
  2. Groq API với `gemma2-9b-it` (Model đã bị Groq decommission).
  3. Groq API với `llama-3.1-8b-instant` (8B parameters, miễn phí, tốc độ cao).
- **Phương án đã chọn:** Groq API với `llama-3.1-8b-instant`.
- **Lý do:** Đáp ứng chính xác tiêu chí ≤ 10B parameters (8B), thời gian phản hồi nhanh (~1s/request), hỗ trợ tốt JSON output format.
- **Bằng chứng quyết định phù hợp:** Kết quả chạy 50 cases hoàn thành suôn sẻ với `llama-3.1-8b-instant`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `HTTP Error 403: error code: 1010` khi gọi Groq API qua `urllib.request`.
- **Lệnh hoặc bước tái hiện:** `python src/test_llm.py`
- **Nguyên nhân gốc:** Cloudflare bảo vệ Groq API chặn các HTTP request không có `User-Agent` header chuẩn.
- **Cách xử lý:** Thêm `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) MultiAgentDisputeResolver/1.0` vào header trong `llm_client.py`.
- **Cách xác minh sau khi sửa:** Lệnh `python src/test_llm.py` trả về `SUCCESS` và nhận response JSON từ LLM.
- **Bài học kỹ thuật:** Luôn cấu hình đầy đủ User-Agent khi sử dụng `urllib.request` làm REST client với các API công cộng có WAF/Cloudflare.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Dữ liệu đi từ khiếu nại (input case) đến quyết định giải quyết như thế nào?**  
   Dữ liệu từ file JSON khiếu nại (`input/EC_XXX.json`) chứa `claimed_order_id`. CoordinatorAgent nhận case_id và gọi OrderAgent tra cứu thông tin đơn hàng trong dữ liệu gốc CSV của Olist. OrderAgent chuyển dữ liệu cấu trúc `order_info` sang cho DeliveryAgent và PaymentAgent để kiểm tra thời gian giao thực tế vs ước tính và đối soát các dòng thanh toán. Toàn bộ bằng chứng từ 3 agent trên được tập hợp chuyển đến PolicyAgent để áp dụng quy tắc nghiệp vụ `EC_POLICY_V1` (thông qua mô hình LLM `llama-3.1-8b-instant`), sau đó VerifierAgent kiểm định schema, giới hạn phần tử và ghi kết quả ra file JSON ở folder `output/`.

2. **Evaluation set và ground-truth document/evidence IDs dùng để đo chất lượng ra sao?**  
   Evaluation set bao gồm 50 file JSON khiếu nại (`EC_001.json` đến `EC_050.json`). Mỗi case có tập bằng chứng chuẩn (ground-truth evidence IDs) được sinh trực tiếp từ các khóa trong CSV (`order:<id>`, `item:<order_id>:<item_id>`, `payment:<order_id>:<seq>`, `seller:<seller_id>`, `policy:<root_cause_code>`). Chất lượng của hệ thống được đo bằng độ chính xác của tập evidence IDs, việc xác định đúng bên chịu trách nhiệm (responsible_party), khoản tiền hoàn (recommended_refund_brl) và hành động xử lý (resolution_actions).

3. **Quality checks khác Freshness monitoring ở điểm nào trong bài lab?**  
   - **Quality checks:** Kiểm tra tính hợp lệ về mặt định dạng, tính nhất quán của dữ liệu (schema validation, kiểm tra giới hạn mảng max limits: max 5 entity IDs, 10 evidence IDs, 3 root causes, 3 responsible parties; kiểm tra số tiền hoàn không vượt quá số tiền đã thanh toán và kiểm tra confidence trong đoạn [0, 1]).
   - **Freshness monitoring:** Giám sát mốc thời gian thực tế của đơn hàng (`order_purchase_timestamp`, `shipping_limit_date`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`) để đảm bảo không áp dụng quy tắc hết hạn hoặc sai lệch thời gian.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**  
   Sử dụng cùng một test set 50 khiếu nại chuẩn (`EC_001` - `EC_050`) giúp đảm bảo tính công bằng và có thể so sánh trực tiếp (fair & reproducible comparison) giữa các kiến trúc agent khác nhau (như Rule-based baseline vs Multi-Agent LLM). Việc này cho phép đo lường chính xác mức độ cải thiện về khả năng phân tích lý do gốc (root cause analysis), độ tin cậy (confidence score) và giảm thiểu hiện tượng hallucination của LLM.

5. **Repair / Resolution được xem là thành công dựa trên artifact và metric nào?**  
   - **Artifact:**  
     1. 50 file kết quả JSON trong thư mục `output/` tuân thủ 100% Output Schema.  
     2. Nhật ký chạy thực tế `logging/trace.jsonl` chứa đúng 300 trace entries phản ánh 6 bước handoff của các Agent cho 50 cases.  
     3. Báo cáo cấu hình `logging/metadata.json` khai báo đúng mô hình LLM (`llama-3.1-8b-instant`, parameter size `8B`).  
   - **Metrics:** Điểm tổng hợp có trọng số theo đề bài (20% Primary issue & confidence, 20% Affected entities, 15% Root cause & responsible parties, 15% Evidence IDs, 20% Financial resolution, 10% Resolution actions) đạt tối đa và 0 case bị lỗi hard gate.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Đình Khánh  
**Ngày xác nhận:** 2026-08-05
