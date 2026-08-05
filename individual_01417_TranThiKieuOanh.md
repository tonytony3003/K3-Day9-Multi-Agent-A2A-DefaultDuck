# Báo cáo cá nhân — Trần Thị Kiều Oanh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Thị Kiều Oanh |
| MSSV | 2A202601417 |
| Khóa/Lớp | K3 |
| Vai trò chính | Policy Agent và Output Builder |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Policy mapping | `src/policy_engine.py` — `POLICY` | `EC_POLICY_V1` | Cause, party, refund, action, confidence | Hoàn thành |
| Rule precedence | `evaluate_policy` | Ba specialist findings | Một primary issue | Hoàn thành |
| Output builder | `build_output` | Input case và Data Catalog | `OutputCase` draft | Hoàn thành |
| Schema contract | `src/models.py` | Draft fields | Strict Pydantic output | Hoàn thành |

## 3. Kết quả bàn giao

- Cài đặt đủ sáu policy rule theo đúng thứ tự ưu tiên.
- Mapping chính xác root cause, responsible party, refund và action.
- Tạo affected entities và evidence IDs có nguồn trong CSV/policy.
- Confidence cố định theo rule để các case tương đương nhất quán.

## 4. Giải thích kỹ thuật

Policy không chọn rule theo nội dung ngôn ngữ tự nhiên. `evaluate_policy` đọc facts đã chuẩn hóa và kiểm tra lần lượt canceled, unavailable, seller delay, logistics delay, split payment và unsupported claim. `build_output` dùng kết quả này để dựng một `OutputCase` hoàn chỉnh; mọi số tiền đến từ Data Catalog, không do LLM tự cộng.

| Thành phần | Contract |
| --- | --- |
| Input | Order/Seller, Payment và Delivery findings |
| Output | Primary issue và output draft đúng schema |
| Module sử dụng | Verifier và atomic writer |
| Lỗi phải chặn | Không rule nào match, sai policy version, thiếu responsible seller |

### Cách xác minh

```powershell
python -m pytest -q
python -m src.main --mode deterministic --no-progress
```

Golden distribution: mỗi nhóm canceled/unavailable/seller/logistics có 8 case; split và unsupported có 9 case.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** một order có thể đồng thời có nhiều payment và giao trễ.
- **Phương án:** chọn rule bằng claim/LLM hoặc dùng ordered policy engine.
- **Lựa chọn:** ordered deterministic policy engine.
- **Lý do:** bảo đảm rule ưu tiên cao hơn luôn thắng, ví dụ canceled paid phải full refund thay vì giải thích split payment.
- **Bằng chứng:** unit test `canceled over split payment` pass.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** strict structured output bị OpenAI từ chối do `risk_flags` không có trong `required`.
- **Nguyên nhân:** field có default khiến JSON Schema coi là optional, không tương thích strict mode.
- **Xử lý:** yêu cầu agent luôn trả `risk_flags`, dùng `[]` nếu không có cảnh báo.
- **Xác minh:** schema test xác nhận `required == properties`; LLM smoke-test pass.

## 7. Hiểu biết end-to-end

Policy Agent chỉ chạy sau fan-in. Agent nhận ba finding nhỏ thay vì raw CSV, gọi policy-as-code, dựng draft và chuyển Verifier. Nếu source và mô tả LLM mâu thuẫn, rule engine/source data là nguồn sự thật cuối.

## 8. Cam kết

- [x] Hiểu và áp đúng policy precedence.
- [x] Không chọn rule dựa trên claim text.
- [x] Output tuân thủ Pydantic schema và entity limits.
- [x] Không ghi secret trong báo cáo.

**Họ và tên:** Trần Thị Kiều Oanh  
**Ngày xác nhận:** 2026-08-05

