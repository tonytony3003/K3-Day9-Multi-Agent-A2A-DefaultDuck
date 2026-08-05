# Báo cáo cá nhân — Lê Thị Thuý

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Thị Thuý |
| MSSV | 2A202601381 |
| Khóa/Lớp | K3 |
| Vai trò chính | Coordinator Agent và LangGraph orchestration |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Điều phối workflow | `src/graph.py` — `CaseState`, `build_graph`, `coordinator` | `InputCase` | Investigation plan và graph state | Hoàn thành |
| Fan-out/fan-in specialist | `src/graph.py` | Kế hoạch điều tra | Ba specialist findings | Hoàn thành |
| Runner 50 case | `src/main.py` | `input/EC_*.json` | Output, trace và metadata | Hoàn thành |

Phạm vi của Coordinator là điều phối, không tự quyết định primary issue. Node này luôn dispatch đủ Order/Seller, Payment và Delivery, sau đó chỉ cho Policy chạy khi ba nhánh đã hoàn tất.

## 3. Kết quả bàn giao

- Graph có luồng `Coordinator -> [Order/Seller || Payment || Delivery] -> Policy -> Verifier`.
- Ba specialist chạy song song và ghi finding vào các khóa state tách biệt.
- Mỗi case chỉ được ghi output sau khi Verifier trả kết quả không có lỗi.
- Full deterministic audit sinh đủ 50 output với phân bố `8/8/8/8/9/9` và tổng refund `3429.64 BRL`.

## 4. Giải thích kỹ thuật

Coordinator nhận `case_id`, `claimed_order_id` và `policy_version`, tạo kế hoạch có danh sách ba agent bắt buộc. LangGraph sử dụng ba edge từ Coordinator để fan-out; edge join dạng danh sách bảo đảm Policy chờ đủ ba nhánh. Shared state chỉ chứa Pydantic model và dictionary có cấu trúc, không chứa toàn bộ CSV hoặc chain-of-thought.

| Thành phần | Contract |
| --- | --- |
| Input | `InputCase` đã qua Pydantic validation |
| Output | `plan`, specialist findings, draft và verified output trong `CaseState` |
| Module phụ thuộc | `data_catalog`, `policy_engine`, `llm_client`, `trace_logger` |
| Lỗi phải xử lý | Thiếu input, order không tồn tại, specialist/API fail, verifier fail |

### Cách xác minh

```powershell
python -m pytest -q
python -m src.main --mode deterministic --case EC_001
python -m src.main --mode deterministic --no-progress
```

Kết quả thực tế: test pass, đủ 50 output và submission audit `passed=true`.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** cần thể hiện multi-agent thật nhưng policy và phép tính phải ổn định.
- **Phương án cân nhắc:** group chat tự do; custom tuần tự; LangGraph có state và routing xác định.
- **Lựa chọn:** LangGraph fan-out/fan-in.
- **Lý do:** handoff rõ, specialist chạy song song, dễ trace và không để LLM chọn sai thứ tự policy.
- **Bằng chứng:** trace có event theo từng agent/case; aggregate audit khớp dữ liệu.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** specialist trả `accepted=false` khi phát hiện giao trễ khiến graph dừng dù payload đúng.
- **Nguyên nhân:** semantic của `accepted` chưa phân biệt business issue với malformed handoff.
- **Xử lý:** business issue được ghi warning; chỉ deterministic Verifier có quyền chặn output.
- **Xác minh:** smoke-test `EC_001` và `EC_003` đi qua đủ sáu agent.

## 7. Hiểu biết end-to-end

Input cung cấp order ID. Data Catalog lấy order, items và payments; ba specialist phân tích độc lập. Policy engine áp sáu rule theo precedence; Policy dựng output; Verifier tái tính entity, evidence và tài chính; writer ghi JSON atomic; batch audit kiểm tra đủ 50 file. Claim của khách chỉ định hướng điều tra, không phải bằng chứng.

## 8. Cam kết

- [x] Báo cáo phản ánh đúng phần việc được phân công.
- [x] Có thể giải thích luồng end-to-end và contract giữa các agent.
- [x] Không ghi secret hoặc nội dung `.env`.
- [x] Kết quả nêu trong báo cáo có lệnh/artifact kiểm chứng.

**Họ và tên:** Lê Thị Thuý  
**Ngày xác nhận:** 2026-08-05

