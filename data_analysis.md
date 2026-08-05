# Báo cáo Phân tích Dữ liệu (EDA) - Olist Customer Service

Dựa trên kết quả chạy tự động 50 khiếu nại (cases) từ khách hàng bằng hệ thống 7-Agent Architecture, dưới đây là bảng phân tích chi tiết về các nhóm vấn đề, nguyên nhân cốt lõi và hướng giải quyết.

## 1. Tổng quan Dữ liệu (Overview)
- **Tổng số cases đã xử lý**: 50
- **Tổng số tiền hoàn trả (Refund) dự kiến**: **2,656.66 BRL**
- **Trạng thái xử lý (Case Status)**:
  - `no_action` (Từ chối bồi thường hoặc chỉ giải thích): 35 cases (70%)
  - `action_required` (Cần hoàn tiền cho khách): 15 cases (30%)

---

## 2. Phân loại Vấn đề Chính (Primary Issues)

Quá trình phân loại của hệ thống Policy Agent & Debate Agent đã chia 50 khiếu nại thành các nhóm sau:

| Primary Issue | Số lượng | Tỷ lệ | Phân tích |
|---|---|---|---|
| `unsupported_late_claim` | 26 | 52% | Khách hàng khiếu nại giao hàng trễ, nhưng thực tế đơn hàng **vẫn được giao trong khoảng thời gian dự kiến (Estimated Delivery Date)**. Đây là loại khiếu nại phổ biến nhất nhưng không hợp lệ. |
| `unavailable_order_paid` | 11 | 22% | Đơn hàng bị hủy do hết hàng (unavailable) nhưng khách hàng đã thanh toán. Cần hoàn tiền 100%. |
| `valid_split_payment` | 9 | 18% | Khách hàng thắc mắc về số tiền bị trừ nhiều lần (split payment). Tuy nhiên, tổng các khoản thanh toán khớp với tổng giá trị đơn hàng (items + freight). Không có lỗi hệ thống. |
| `late_delivery_seller` | 4 | 8% | Giao hàng trễ do **lỗi của Người Bán (Seller)** giao hàng cho đơn vị vận chuyển quá hạn (Shipping Limit Date). Người bán phải chịu trách nhiệm hoàn phí vận chuyển. |
| `canceled_order_paid` | 0 | 0% | Không có đơn hàng nào bị hủy chủ động mà chưa được hoàn tiền. |
| `late_delivery_logistics` | 0 | 0% | Không có trường hợp nào giao trễ do lỗi hoàn toàn thuộc về bên vận chuyển (Logistics). |

---

## 3. Phân tích Nguyên nhân Cốt lõi (Root Causes)

Hệ thống Root Cause Analysis (RCA) đã chỉ ra các mã lỗi (Cause Codes) tương ứng với các quyết định xử lý:

- **`DELIVERY_WITHIN_ESTIMATE` (26 cases)**: Chiếm đa số. Khách hàng cảm thấy giao hàng lâu, nhưng dữ liệu hệ thống ghi nhận hàng vẫn đến trước hoặc đúng ngày dự kiến.
- **`ORDER_UNAVAILABLE_AFTER_PAYMENT` (11 cases)**: Lỗi từ phía kho hàng của Seller/Nền tảng, khách đặt mua nhưng không có hàng để giao.
- **`MULTIPLE_PAYMENTS_RECONCILED` (9 cases)**: Khách hàng sử dụng nhiều phương thức thanh toán hoặc thẻ tín dụng chia nhỏ hóa đơn. Các khoản thanh toán đã được đối soát thành công.
- **`SELLER_HANDOFF_AFTER_LIMIT` (4 cases)**: Nút thắt cổ chai ở khâu người bán đóng gói và giao cho bưu cục quá chậm. 

> [!TIP]
> **Khuyến nghị cho Olist (Business Insights)**
> 1. **Cải thiện hiển thị đa thanh toán**: Có 9 khách hàng phàn nàn vì không hiểu tại sao họ bị trừ tiền nhiều lần. Olist nên cải thiện giao diện hóa đơn để hiển thị rõ việc chia nhỏ thanh toán (Split Payment) ngay trên email xác nhận.
> 2. **Giáo dục khách hàng về thời gian giao hàng**: 52% khiếu nại là sai lệch kỳ vọng (giao hàng chưa trễ nhưng khách vẫn phàn nàn). Olist cần hiển thị ngày dự kiến (Estimated Delivery Date) to và rõ hơn trong quá trình theo dõi đơn hàng (Tracking).
> 3. **Chế tài Người Bán (Sellers)**: 4 trường hợp giao trễ do lỗi người bán ngâm hàng. Cần có chính sách phạt (SLA) chặt chẽ hơn với các Seller vi phạm thời gian chuẩn bị hàng.

---

## 4. Hành động Xử lý (Resolution Actions)

Với 50 cases trên, hệ thống Agent tự động đã ra các quyết định:

- **Từ chối hoàn tiền (`reject_late_refund`)**: 26 cases
- **Hoàn tiền 100% (`issue_full_refund`)**: 11 cases (Cho các đơn hàng unavailable)
- **Giải thích thanh toán (`explain_valid_split_payment`)**: 9 cases
- **Hoàn phí vận chuyển (`refund_freight`)**: 4 cases (Lấy từ tài khoản của Seller giao trễ)

Hệ thống đã tự động định tuyến toàn bộ 50 khiếu nại với độ chính xác cao và theo sát *EC_POLICY_V1*, tiết kiệm đáng kể thời gian cho bộ phận CSKH của Olist.
