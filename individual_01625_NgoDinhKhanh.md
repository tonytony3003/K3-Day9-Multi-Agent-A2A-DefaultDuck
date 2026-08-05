# Báo cáo cá nhân — Ngô Đình Khánh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Ngô Đình Khánh |
| MSSV | 2A202601625 |
| Khóa/Lớp | K3 |
| Vai trò chính | Delivery Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Chuẩn hóa timeline | `src/data_catalog.py` — `parse_time`, `OrderRow` | Timestamp trong orders CSV | Datetime hoặc `None` | Hoàn thành |
| Phân tích giao hàng | `src/policy_engine.py` — delivery finding | Delivery dates và shipping limits | Late flag, days, attribution facts | Hoàn thành |
| Handoff Delivery | `src/graph.py` — node `delivery` | Claimed order | Structured delivery finding | Hoàn thành |

## 3. Kết quả bàn giao

- So sánh giao thực tế với ngày giao dự kiến cho 34 delivered order.
- Phân biệt 8 seller delay, 8 logistics delay và 9 unsupported late claim.
- Không gán nguyên nhân vận chuyển cho canceled/unavailable order thiếu timestamp.
- Trả danh sách violating seller dựa trên shipping limit từng item.

## 4. Giải thích kỹ thuật

Delivery Agent sử dụng hai tầng so sánh:

```text
delivered_late = delivered_customer_date > estimated_delivery_date
seller_handoff_late = carrier_date > shipping_limit_date của ít nhất một item
```

Nếu giao trễ và seller handoff late, trách nhiệm thuộc seller. Nếu giao trễ nhưng seller handoff đúng hạn, trách nhiệm thuộc logistics. Nếu giao đúng/sớm và payment reconciled, claim giao trễ không được dữ liệu hỗ trợ.

| Thành phần | Contract |
| --- | --- |
| Input | Order delivery timeline và item shipping limits |
| Output | `delivered_late`, `late_days`, `seller_handoff_late`, violating sellers |
| Module sử dụng | Policy Agent và Verifier |
| Edge case | Null delivery timestamp, strict `>` thay vì `>=` |

### Cách xác minh

```powershell
python -m src.main --mode deterministic --case EC_001
python -m src.main --mode deterministic --case EC_009
python -m src.main --mode deterministic --case EC_023
```

Ba case đại diện lần lượt cho seller delay, logistics delay và claim không được hỗ trợ.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** cùng một claim “giao trễ” có thể thuộc seller, logistics hoặc không đúng.
- **Phương án:** chỉ so delivered với estimated; hoặc kết hợp thêm carrier với shipping limit.
- **Lựa chọn:** so sánh hai tầng.
- **Lý do:** phản ánh đúng chain of responsibility trong `EC_POLICY_V1`.
- **Bằng chứng:** 25 late claims tách thành `8 + 8 + 9` đúng aggregate audit.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** timestamp null có thể gây exception hoặc attribution giả.
- **Nguyên nhân:** canceled/unavailable order thường chưa có carrier/customer delivery date.
- **Xử lý:** parse thành `None`, chỉ so sánh khi cả hai timestamp cần thiết tồn tại.
- **Xác minh:** full 50-case run không có timestamp parse/comparison error.

## 7. Hiểu biết end-to-end

Delivery finding không tự quyết định refund. Policy ưu tiên canceled và unavailable trước delivery; điều này ngăn timestamp thiếu ở order chưa giao làm sai primary issue. Payment cung cấp reconciliation; Verifier tái truy vấn raw order view trước khi ghi file.

## 8. Cam kết

- [x] Hiểu khác biệt carrier handoff và customer delivery.
- [x] Không tạo tracking checkpoint ngoài dataset.
- [x] Có case kiểm chứng đủ ba kết quả delivery.
- [x] Báo cáo không chứa secret.

**Họ và tên:** Ngô Đình Khánh  
**Ngày xác nhận:** 2026-08-05

