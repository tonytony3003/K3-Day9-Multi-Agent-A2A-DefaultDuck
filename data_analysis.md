# Phân tích dữ liệu — K3 Day 9 Multi-Agent A2A

## 1. Mục tiêu và phạm vi

Tài liệu này mô tả dữ liệu đầu vào của bài toán giải quyết tranh chấp thương mại điện tử. Phạm vi phân tích gồm:

- 9 bảng CSV trong `data/` thuộc bộ Brazilian E-Commerce Public Dataset by Olist.
- 50 hồ sơ khiếu nại từ `input/EC_001.json` đến `input/EC_050.json`.
- Các quan hệ join, mức độ đầy đủ, chất lượng dữ liệu và phân bố tình huống nghiệp vụ của 50 case.

Các số liệu được tính trực tiếp từ dữ liệu hiện có trong repo. Việc phân loại case tuân theo thứ tự ưu tiên của `EC_POLICY_V1` trong `README.md`.

## 2. Tổng quan dữ liệu Olist

| File | Số dòng dữ liệu | Số cột | Vai trò |
| --- | ---: | ---: | --- |
| `olist_orders_dataset.csv` | 99.441 | 8 | Trạng thái đơn và các mốc thời gian mua, duyệt, bàn giao, giao thực tế, giao dự kiến |
| `olist_order_items_dataset.csv` | 112.650 | 7 | Sản phẩm, seller, giá, phí vận chuyển và hạn bàn giao của từng item |
| `olist_order_payments_dataset.csv` | 103.886 | 5 | Các dòng thanh toán của đơn hàng |
| `olist_order_reviews_dataset.csv` | 99.224 | 7 | Điểm và nội dung đánh giá của khách hàng |
| `olist_customers_dataset.csv` | 99.441 | 5 | Khách hàng và khu vực nhận hàng |
| `olist_products_dataset.csv` | 32.951 | 9 | Danh mục, kích thước và khối lượng sản phẩm |
| `olist_sellers_dataset.csv` | 3.095 | 4 | Seller và khu vực của seller |
| `olist_geolocation_dataset.csv` | 1.000.163 | 5 | Tọa độ và địa danh theo zip-code prefix |
| `product_category_name_translation.csv` | 71 | 2 | Ánh xạ tên danh mục tiếng Bồ Đào Nha sang tiếng Anh |

Khoảng thời gian mua hàng toàn bộ dataset là từ `2016-09-04 21:15:19` đến `2018-10-17 17:30:18`. Trạng thái đơn hàng toàn cục gồm:

| Trạng thái | Số đơn |
| --- | ---: |
| `delivered` | 96.478 |
| `canceled` | 625 |
| `unavailable` | 609 |
| `shipped` | 1.107 |
| `invoiced` | 314 |
| `processing` | 301 |
| `created` | 5 |
| `approved` | 2 |

## 3. Data dictionary và khóa chính

### 3.1. Orders

`olist_orders_dataset.csv` là bảng trung tâm, một dòng tương ứng một đơn hàng.

| Trường | Ý nghĩa |
| --- | --- |
| `order_id` | Định danh đơn hàng; khóa dùng để nối items, payments và reviews |
| `customer_id` | Định danh khách hàng trong phạm vi một order; nối sang bảng customers |
| `order_status` | Trạng thái hiện tại của đơn |
| `order_purchase_timestamp` | Thời điểm đặt hàng |
| `order_approved_at` | Thời điểm thanh toán/đơn được duyệt |
| `order_delivered_carrier_date` | Thời điểm đơn được bàn giao cho đơn vị vận chuyển |
| `order_delivered_customer_date` | Thời điểm giao thực tế cho khách |
| `order_estimated_delivery_date` | Hạn giao dự kiến |

Hai phép so sánh thời gian quan trọng:

- Giao trễ: `order_delivered_customer_date > order_estimated_delivery_date`.
- Seller bàn giao trễ: `order_delivered_carrier_date > shipping_limit_date` của ít nhất một item thuộc seller đó.

### 3.2. Order items

`olist_order_items_dataset.csv` có quan hệ một-nhiều với orders. Khóa logic của một item là `(order_id, order_item_id)`.

- `price` là giá item, chưa gồm vận chuyển.
- `freight_value` là phí vận chuyển của item.
- `shipping_limit_date` là hạn seller phải bàn giao item.
- `product_id` và `seller_id` nối sang bảng products và sellers.

Tổng giá trị hàng và phí vận chuyển của một order phải được cộng trên tất cả item, không lấy một dòng đại diện.

### 3.3. Payments

`olist_order_payments_dataset.csv` cũng có quan hệ một-nhiều với orders. Khóa logic là `(order_id, payment_sequential)`.

- `payment_value` là giá trị của từng dòng thanh toán.
- `payment_installments` là số kỳ trả góp, không phải số dòng thanh toán.
- Một order có nhiều dòng payment không đồng nghĩa với thu trùng.

Phép đối soát được dùng trong bài:

```text
payment_total = SUM(payment_value)
expected_total = SUM(price) + SUM(freight_value)
reconciled = ABS(payment_total - expected_total) <= 0.10 BRL
```

### 3.4. Customers, products, sellers và geolocation

- `customer_id` chỉ nhận diện customer gắn với một order. Muốn nhận diện cùng người qua nhiều order phải dùng `customer_unique_id`.
- `product_id` nối item với thông tin danh mục và kích thước sản phẩm.
- `seller_id` nối item với seller chịu trách nhiệm.
- Các trường `*_zip_code_prefix` có thể nối với `geolocation_zip_code_prefix`. Bảng geolocation có nhiều dòng cho cùng zip-code prefix, vì vậy phải aggregate/deduplicate trước khi join để tránh nhân bản dòng và làm sai tổng tiền.

## 4. Sơ đồ quan hệ

```text
input/EC_xxx.json
  └── customer_request.claimed_order_id
          │
          ▼
       orders ── customer_id ──► customers
          │
          ├── order_id ──► order_items ── product_id ──► products ──► category translation
          │                       └────── seller_id ───► sellers
          ├── order_id ──► order_payments
          └── order_id ──► order_reviews

customers/sellers ── zip_code_prefix ──► geolocation (aggregate trước khi join)
```

## 5. Phân tích 50 input case

### 5.1. Tính hợp lệ và độ phủ

| Kiểm tra | Kết quả |
| --- | ---: |
| File input đúng dải `EC_001`–`EC_050` | 50/50 |
| `case_id` duy nhất | 50/50 |
| `claimed_order_id` duy nhất | 50/50 |
| Order tìm thấy trong bảng orders | 50/50 |
| Order có ít nhất một payment | 50/50 |
| Ngôn ngữ `vi` | 50/50 |
| Policy `EC_POLICY_V1` | 50/50 |
| `opened_at = 2018-10-18T00:00:00-03:00` | 50/50 |

50 order liên kết tới 48 item row, 60 payment row, 50 review row, 50 customer, 42 product duy nhất và 40 seller duy nhất.

Có 8 order không có item row. Cả 8 đều mang trạng thái `unavailable`; đây là tình huống hợp lệ theo đề bài. Với các order này, pipeline phải:

- Để `item_ids` và `seller_ids` rỗng.
- Đặt `item_total_brl = 0.0` và `freight_total_brl = 0.0`.
- Lấy số tiền hoàn toàn phần từ tổng `payment_value`, không suy diễn item không tồn tại.

### 5.2. Nội dung khiếu nại

| Nhóm thông điệp | Số case |
| --- | ---: |
| Khách cho rằng đơn giao trễ | 25 |
| Đơn không hoàn tất dù đã thanh toán | 16 |
| Khách lo bị thu trùng do có nhiều dòng payment | 9 |

Lời khiếu nại chỉ dùng để xác định mục tiêu điều tra. Kết luận phải dựa trên dữ liệu join được, không mặc định lời khách hàng là đúng.

### 5.3. Phân bố trạng thái và độ phức tạp

| Thuộc tính | Phân bố |
| --- | --- |
| Trạng thái order | 34 `delivered`, 8 `canceled`, 8 `unavailable` |
| Số item row/order | 38 đơn có 1; 2 đơn có 2; 2 đơn có 3; 8 đơn không có item |
| Số payment row/order | 41 đơn có 1; 8 đơn có 2; 1 đơn có 3 |
| Số seller/order | 42 đơn có 1 seller; 8 đơn không có seller do không có item |

Không có order nhiều seller trong bộ 50 case. Tuy vậy, pipeline vẫn nên group theo seller để không phụ thuộc vào đặc điểm riêng của benchmark này.

### 5.4. Phân loại theo `EC_POLICY_V1`

Khi áp dụng đúng thứ tự ưu tiên trong policy, 50 case được chia thành sáu nhóm:

| Primary issue | Số case | Tỷ lệ | Resolution |
| --- | ---: | ---: | --- |
| `late_delivery_seller` | 8 | 16% | Hoàn tổng freight; seller chịu trách nhiệm |
| `late_delivery_logistics` | 8 | 16% | Hoàn tổng freight; logistics chịu trách nhiệm |
| `canceled_order_paid` | 8 | 16% | Hoàn toàn bộ payment; platform chịu trách nhiệm |
| `unavailable_order_paid` | 8 | 16% | Hoàn toàn bộ payment; platform chịu trách nhiệm |
| `valid_split_payment` | 9 | 18% | Không hoàn; giải thích payment hợp lệ |
| `unsupported_late_claim` | 9 | 18% | Không hoàn; bác yêu cầu hoàn do giao đúng hạn |

Tổng cộng có 32 case `action_required` và 18 case `no_action`.

Phân bố này cho thấy benchmark được thiết kế khá cân bằng. Ba nhóm thông điệp đầu vào ánh xạ chính xác tới các nhánh cần điều tra:

- 25 claim giao trễ → 8 lỗi seller, 8 lỗi logistics, 9 claim không được dữ liệu hỗ trợ.
- 16 claim đơn không hoàn tất → 8 đơn canceled đã trả tiền, 8 đơn unavailable đã trả tiền.
- 9 claim payment bị lặp → cả 9 là split payment hợp lệ sau đối soát.

### 5.5. Thống kê giao hàng và tài chính

Trong 34 order `delivered`:

- 16 order giao sau ngày dự kiến.
- 18 order giao đúng hoặc sớm hơn dự kiến.
- Chênh lệch `delivered - estimated` nằm trong khoảng `-27,48` đến `+12,57` ngày; trung bình `-3,41` ngày.

Tổng trên 50 case:

| Chỉ số | Giá trị |
| --- | ---: |
| Tổng giá item | 4.686,52 BRL |
| Tổng freight | 727,47 BRL |
| Tổng payment | 7.782,89 BRL |
| Order khớp payment với item + freight trong sai số 0,10 BRL | 42/50 |

8 order không đối soát được với item + freight chính là 8 order `unavailable` không có item row. Tổng payment của nhóm này là `2.368,90 BRL`; không nên coi chênh lệch này là lỗi thanh toán.

Nếu áp dụng policy, tổng refund đề xuất cho 32 case cần xử lý là `3.429,64 BRL`:

| Nhóm refund | Số tiền |
| --- | ---: |
| Full refund cho `canceled_order_paid` | 789,26 BRL |
| Full refund cho `unavailable_order_paid` | 2.368,90 BRL |
| Freight refund cho `late_delivery_seller` | 177,54 BRL |
| Freight refund cho `late_delivery_logistics` | 93,94 BRL |

## 6. Chất lượng dữ liệu và rủi ro xử lý

### 6.1. Giá trị thiếu toàn cục

- Orders thiếu `order_approved_at`: 160 dòng.
- Orders thiếu `order_delivered_carrier_date`: 1.783 dòng.
- Orders thiếu `order_delivered_customer_date`: 2.965 dòng.
- Products thiếu nhóm thông tin tên/danh mục/ảnh: 610 dòng; thiếu kích thước/khối lượng: 2 dòng.
- Reviews thiếu tiêu đề: 87.658 dòng; thiếu nội dung: 58.274 dòng.

Các timestamp giao hàng trống thường phù hợp với trạng thái chưa giao, canceled hoặc unavailable; không được tự tạo timestamp thay thế. Review text cũng không cần thiết cho sáu policy hiện tại.

### 6.2. Các rủi ro dễ gây sai kết quả

1. Join trực tiếp geolocation theo zip-code làm nhân bản item/payment và tăng sai tổng tiền.
2. Chỉ lấy payment đầu tiên thay vì cộng tất cả `payment_value` làm sai split payment.
3. Nhân `payment_value` với `payment_installments` làm phóng đại tổng thanh toán.
4. So sánh carrier date với một shipping limit đại diện làm bỏ sót item/seller bàn giao trễ.
5. Kết luận logistics chịu trách nhiệm chỉ vì giao trễ mà không kiểm tra seller handoff.
6. Bắt buộc order phải có item sẽ loại sai các order unavailable hợp lệ.
7. Dùng số thực nhị phân không làm tròn có thể gây sai tại ngưỡng đối soát 0,10 BRL; nên dùng `Decimal` hoặc làm tròn 2 chữ số.
8. Dùng `customer_id` để nhận diện khách hàng xuyên nhiều order thay vì `customer_unique_id`.

## 7. Dữ liệu không cung cấp

Dataset không có refund ledger, transaction ID của giao dịch hoàn tiền, tracking checkpoint theo item hoặc bằng chứng trực tiếp về giao sai/giao thiếu. Vì vậy hệ thống không nên tạo evidence hay sự kiện thuộc các loại này. Evidence chỉ nên được dựng từ order, item, payment, seller và policy record có thật.

## 8. Khuyến nghị cho pipeline multi-agent

- Load và chuẩn hóa các bảng một lần, sau đó cung cấp view theo `order_id` cho các agent để tránh mỗi agent đọc lại toàn bộ CSV.
- Giữ số tiền bằng `Decimal`, tổng hợp theo order trước khi áp policy.
- Áp policy theo đúng thứ tự ưu tiên: trạng thái paid canceled/unavailable trước, giao trễ tiếp theo, split payment rồi mới unsupported claim.
- Tách rõ timestamp giao khách, timestamp carrier nhận hàng và shipping limit của từng item.
- Verifier phải kiểm tra entity/evidence ID thực sự tồn tại trong CSV, schema output, giới hạn số phần tử và phép cộng tài chính.
- Không cần dùng geolocation, products hoặc reviews để quyết định sáu primary issue hiện tại; các bảng này chỉ bổ sung ngữ cảnh. Giảm quyền truy cập theo vai trò giúp pipeline đơn giản và hạn chế join sai.

## 9. Kết luận

Bộ 50 input hiện tại đầy đủ, không có order ID bị thiếu và bao phủ cân bằng cả sáu nhánh của `EC_POLICY_V1`. Dữ liệu cần thiết để tạo output nằm chủ yếu trong orders, order items và payments. Hai điểm cần xử lý cẩn thận nhất là split payment và các order unavailable không có item. Nếu join đúng cardinality và áp policy đúng thứ tự, toàn bộ 50 case có thể được phân loại xác định mà không cần LLM suy diễn thêm sự kiện.
