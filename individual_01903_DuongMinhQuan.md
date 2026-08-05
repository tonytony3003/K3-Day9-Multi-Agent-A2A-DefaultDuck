# Báo cáo cá nhân — Dương Minh Quân

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Dương Minh Quân |
| MSSV | 2A202601903 |
| Khóa/Lớp | K3 |
| Vai trò chính | Verifier Agent, validation và observability |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Per-case verifier | `src/validation.py` — `validate_output` | Case, draft, catalog | Danh sách invariant errors | Hoàn thành |
| Submission audit | `audit_submission` | 50 input/output | Aggregate audit | Hoàn thành |
| Trace | `src/trace_logger.py` | Workflow events | `logging/trace.jsonl` | Hoàn thành |
| Metadata/writer | `src/main.py`, `atomic_write_json` | Verified output/run stats | JSON atomic và metadata | Hoàn thành |
| Tests | `tests/test_pipeline.py` | Representative cases | Regression report | Hoàn thành |

## 3. Kết quả bàn giao

- Kiểm tra schema, policy result, entities, evidence, finance, refund, status và action.
- Reject duplicate/không tồn tại evidence ID.
- Hard gate đúng 50 filename và không thiếu output.
- Trace JSONL theo run/case/agent, không chứa API key hoặc chain-of-thought.
- Tạo metadata ghi model `openai/gpt-4o-mini`, framework, runtime và audit.

## 4. Giải thích kỹ thuật

Verifier xem draft là dữ liệu không đáng tin và so sánh với kết quả tái tính từ Data Catalog. `OutputCase` chặn field lạ và giới hạn số entity/evidence/action. Writer dùng file `.tmp` rồi replace để tránh JSON dở dang. Batch audit parse lại toàn bộ output, kiểm tra filename, duplicate case ID, issue distribution và tổng refund.

| Thành phần | Contract |
| --- | --- |
| Input | Raw case, draft output và read-only Data Catalog |
| Output | PASS hoặc danh sách lỗi có thể truy vết |
| Module sử dụng | Runner/output writer |
| Hard gate | Schema, policy, evidence existence, totals, limits, file count |

### Cách xác minh

```powershell
python -m pytest -q
python -m src.main --mode deterministic --no-progress
(Get-ChildItem .\output\EC_*.json).Count
(Get-Content .\logging\trace.jsonl).Count
```

Kết quả full deterministic: 50 output, 503 trace events, audit pass và refund `3429.64 BRL`.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** output đúng schema vẫn có thể chứa ID giả hoặc số tiền sai.
- **Phương án:** chỉ dùng JSON Schema; LLM tự review; kết hợp schema với deterministic recomputation.
- **Lựa chọn:** Pydantic + Data Catalog + policy recomputation + batch hard gate.
- **Lý do:** kiểm tra cả hình dạng lẫn ý nghĩa nghiệp vụ.
- **Bằng chứng:** independent raw-data audit không tìm thấy mismatch trên 50 baseline outputs.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** OpenRouter full run dừng với HTTP 402 do reserve `max_tokens` lớn hơn credit còn lại.
- **Nguyên nhân:** mỗi request yêu cầu reserve 300 output tokens dù response review ngắn.
- **Xử lý:** giảm budget xuống 96, rút gọn review và thêm adaptive retry; key preflight chạy trước khi gửi case data.
- **Xác minh:** smoke-test LLM `EC_001` và `EC_003` pass; full run còn phụ thuộc credit tài khoản.

## 7. Hiểu biết end-to-end

Sau khi Coordinator và specialist hoàn tất, Policy dựng draft. Verifier tái kiểm tra trước writer; sau 50 case, submission audit kiểm tra cấp batch. Trace và metadata là bằng chứng workflow, còn file zip nộp chỉ chứa 50 JSON trong output.

## 8. Cam kết

- [x] Kiểm tra được schema lẫn business invariant.
- [x] Trace không chứa secret/chain-of-thought.
- [x] Không đánh dấu pass khi audit còn lỗi.
- [x] Có regression tests cho sáu rule và edge cases.

**Họ và tên:** Dương Minh Quân  
**Ngày xác nhận:** 2026-08-05
