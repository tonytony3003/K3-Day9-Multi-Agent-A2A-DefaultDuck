# Báo cáo cá nhân — Phí Đình Hoàng Anh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phí Đình Hoàng Anh |
| MSSV | 2A202601853 |
| Khóa/Lớp | K3 |
| Vai trò chính | Order & Seller Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phần việc được phân công

| Module | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Index order/item | `src/data_catalog.py` — `DataCatalog` | Orders và order items CSV | Read-only indexes | Hoàn thành |
| Order/Seller finding | `src/policy_engine.py` — `specialist_findings` | `order_id` | Status, item IDs, seller IDs, violating items/sellers | Hoàn thành |
| Evidence order/item/seller | `src/policy_engine.py` | Finding đã chuẩn hóa | Evidence IDs hợp lệ | Hoàn thành |

## 3. Kết quả bàn giao

- Xác minh order tồn tại và lấy đúng status.
- Giữ đầy đủ item của order, không chọn một item đại diện.
- Group seller và xác định seller vi phạm nếu carrier nhận hàng sau shipping limit của ít nhất một item.
- Hỗ trợ đúng 8 unavailable order không có item bằng các danh sách rỗng.

## 4. Giải thích kỹ thuật

Data Catalog parse CSV một lần, tạo `orders` và `items_by_order`. Mỗi item được chuẩn hóa thành `ItemRow` bất biến. Order/Seller finding trả `item_ids`, `seller_ids`, `violating_item_ids`, `violating_seller_ids` và `seller_handoff_late`. Phép so sánh sử dụng timestamp gốc trong CSV:

```text
order_delivered_carrier_date > shipping_limit_date
```

| Thành phần | Contract |
| --- | --- |
| Input | Một `claimed_order_id` đã tồn tại trong orders |
| Output | `order_seller` finding có cấu trúc |
| Module sử dụng output | Delivery Agent, Policy Agent và Verifier |
| Edge case | Order unavailable không item; nhiều item; nhiều shipping limit |

### Cách xác minh

```powershell
python -m pytest -q
python -m src.main --mode deterministic --case EC_001
python -m src.main --mode deterministic --case EC_005
```

`EC_001` kiểm tra seller giao muộn; `EC_005` kiểm tra unavailable không item.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** một order có thể có nhiều item và seller.
- **Phương án:** lấy shipping limit đầu tiên hoặc đánh giá mọi item theo seller.
- **Lựa chọn:** đánh giá mọi item, sau đó group violating seller.
- **Lý do:** tránh bỏ sót seller trễ và tạo đúng item evidence.
- **Bằng chứng:** case nhiều item vẫn có totals/entity đầy đủ; bộ chính thức tối đa ba item.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** unavailable order không có item dễ bị coi là lỗi join.
- **Nguyên nhân:** Olist có payment/order nhưng không có item row cho một số unavailable order.
- **Xử lý:** trả danh sách item/seller rỗng thay vì fail; không suy diễn item.
- **Xác minh:** 8/8 unavailable case có item/freight bằng 0 và full refund payment.

## 7. Hiểu biết end-to-end

Order/Seller finding là một trong ba handoff song song. Payment tính tài chính; Delivery dùng timestamp và violating seller; Policy chọn rule theo precedence. Verifier đối chiếu lại các ID với Data Catalog trước khi writer ghi output.

## 8. Cam kết

- [x] Hiểu cardinality order–item–seller.
- [x] Không tạo seller/item không tồn tại.
- [x] Có lệnh kiểm chứng phần việc.
- [x] Báo cáo không chứa secret.

**Họ và tên:** Phí Đình Hoàng Anh  
**Ngày xác nhận:** 2026-08-05

