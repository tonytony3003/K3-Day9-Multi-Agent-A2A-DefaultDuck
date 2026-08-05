# Báo cáo cá nhân — Ngô Việt Anh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Ngô Việt Anh |
| MSSV | 2A202601579 |
| Khóa/Lớp | K3 |
| Vai trò chính | Payment Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Chuẩn hóa tiền | `src/data_catalog.py` — `money`, `PaymentRow` | Chuỗi số CSV | `Decimal` hai chữ số | Hoàn thành |
| Payment index | `DataCatalog.payments_by_order` | Payments CSV | Payment rows theo order | Hoàn thành |
| Đối soát | `src/policy_engine.py` — payment finding | Items và payments | Totals, delta, split/reconciled flags | Hoàn thành |

## 3. Kết quả bàn giao

- `payment_total = SUM(payment_value)` trên mọi payment row.
- Không nhân payment value với installments.
- `expected_total = SUM(price) + SUM(freight_value)`.
- Đối soát với ngưỡng `abs(delta) <= 0.10 BRL`.
- Xử lý đúng order có 1–3 payment rows và unavailable order không item.

## 4. Giải thích kỹ thuật

Tất cả số tiền được parse trực tiếp thành `Decimal`, quantize `0.01` với `ROUND_HALF_UP`. Finding trả payment IDs, row count, item total, freight total, payment total, reconciliation delta và hai flag `has_split_payment`, `reconciled_within_0_10`.

| Thành phần | Contract |
| --- | --- |
| Input | Items và payments thuộc đúng một order |
| Output | Payment finding với số tiền dạng decimal string |
| Module sử dụng | Policy và Verifier |
| Edge case | Nhiều payment; installments; unavailable không item |

### Cách xác minh

```powershell
python -m pytest -q
python -m src.main --mode deterministic --case EC_030
```

`EC_030` có ba payment rows; payment total phải là `25.84 BRL` và khớp item + freight.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** dùng float hoặc hiểu sai installments có thể làm sai refund.
- **Phương án:** float; integer cents; `Decimal`.
- **Lựa chọn:** `Decimal` và quantize hai chữ số.
- **Lý do:** bám quy tắc BRL, ổn định ở ngưỡng 0.10 và dễ serialize.
- **Bằng chứng:** tổng refund toàn batch là `3429.64 BRL`; audit không có mismatch.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** 8 unavailable order có payment nhưng item total bằng 0, tạo delta lớn.
- **Nguyên nhân:** source không có item rows, không phải payment duplication.
- **Xử lý:** rule unavailable có precedence cao hơn reconciliation; full refund theo payment.
- **Xác minh:** `EC_005` refund `1191.50 BRL` dù item/freight bằng 0.

## 7. Hiểu biết end-to-end

Payment Agent chỉ cung cấp facts tài chính. Agent không tự chọn primary issue. Policy kết hợp status, delivery và payment finding theo precedence; Verifier tái tính lại totals từ CSV và chỉ cho ghi output khi khớp.

## 8. Cam kết

- [x] Hiểu payment row khác installments.
- [x] Dùng Decimal cho toàn bộ phép tính tiền.
- [x] Có test cho split payment và unavailable order.
- [x] Không chứa API key/secret.

**Họ và tên:** Ngô Việt Anh  
**Ngày xác nhận:** 2026-08-05
