# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung            |
| --------------- | ------------------- |
| Họ và tên       | Trần Thị Kiều Oanh  |
| MSSV            | 2A202601417         |
| Khóa/Lớp        | K3                  |
| Vai trò chính   | AI / Multi-Agent Systems Engineer |
| Ngày hoàn thành | 05-08-2026          |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ---------- |
| Multi-Agent Pipeline & Orchestration | `main.py` (`order_seller_agent`, `payment_agent`, `policy_agent`, `verifier_agent`) | 50 file JSON trong `input/` (`EC_001.json` - `EC_050.json`) và 4 file CSV Olist trong `data/` | 50 file JSON trong `output/` tuân thủ Output Schema của `EC_POLICY_V1` | Hoàn thành |
| Agent Trace Logging & Schema Verifier | `main.py` (`verifier_agent`), `trace.jsonl` | Case ID, order ID, quyết định từ Policy Agent và danh sách entities | File `trace.jsonl` tại root repo chứa 50 dòng log handoff chi tiết | Hoàn thành |
| Architecture & Metadata Specs | `architecture.md`, `metadata.json` | Thông số mô hình, phân quyền Agent và sơ đồ luồng dữ liệu | Tài liệu kiến trúc `architecture.md` và file khai báo `metadata.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Sửa lỗi môi trường ảo & cấu hình dependencies | Repo nhóm / Tất cả các Agent | Cài đặt thành công package `pandas`, tạo `requirements.txt` và sửa lỗi di chuyển `trace.jsonl` ra thư mục gốc |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng luồng Multi-Agent xử lý 50 cases khiếu nại | `main.py` | 50 file JSON chuẩn định dạng trong thư mục `output/` | Chạy `python main.py` và kiểm tra 50 file `EC_001.json` - `EC_050.json` |
| Tạo trace log thực thi handoff giữa các Agent | `trace.jsonl` | File `trace.jsonl` ghi lại 5 bước handoff cho từng case | Kiểm tra file `trace.jsonl` có đúng 50 dòng log JSON hợp lệ |
| Đóng gói sản phẩm nộp bài | `output.zip` | File zip chứa đúng 50 file JSON kết quả | Lệnh `zip -j output.zip output/*.json` |

**Bằng chứng Artifact:** File `output.zip` nén đúng 50 file JSON kết quả từ `output/` cùng file trace thực thi `trace.jsonl` tại root repo, đạt 100% tỷ lệ khớp schema, không dính lỗi hard gate (0 điểm).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Tự động hóa quy trình tiếp nhận, đối soát dữ liệu đa nguồn (đơn hàng, người bán, thanh toán, vận chuyển) và đưa ra quyết định xử lý khiếu nại thương mại điện tử cho 50 case khách hàng Olist theo quy tắc nghiệp vụ `EC_POLICY_V1`.

### Cách triển khai

Hệ thống được thiết kế theo mô hình Handoff Multi-Agent:
* **Coordinator Agent**: Đọc file input, khởi tạo context cho case.
* **Order & Seller Agent & Payment Agent**: Truy xuất song song dữ liệu từ các file CSV `orders`, `order_items`, `sellers`, `payments` để tính tổng tiền (`item_total`, `freight_total`, `payment_total`) và lấy mốc thời gian bàn giao.
* **Policy Agent**: Áp dụng chặt chẽ thứ tự ưu tiên của `EC_POLICY_V1`: `canceled_order_paid` > `unavailable_order_paid` > `late_delivery_seller` > `late_delivery_logistics` > `valid_split_payment` > `unsupported_late_claim`.
* **Verifier Agent**: Kiểm tra định dạng Evidence ID (`order:<id>`, `item:<id>:<item_id>`, `payment:<id>:<seq>`, `seller:<id>`, `policy:<code`), áp giới hạn phần tử (tối đa 10 evidence IDs, 5 entity IDs) và xuất ra file JSON kết quả.

### Input, output và contract

| Thành phần               | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | File JSON khiếu nại `input/EC_xxx.json` chứa `claimed_order_id` và các file CSV dữ liệu Olist |
| Output                  | File JSON `output/EC_xxx.json` chứa `assessment`, `affected_entities`, `financial_resolution` và `trace.jsonl` |
| Module phụ thuộc        | `pandas`, `json`, `os`, `datetime`     |
| Module sử dụng output   | Hệ thống chấm điểm tự động (Auto-grader) |
| Điều kiện lỗi cần xử lý | Lỗi thiếu thư viện `pandas`, đường dẫn `trace.jsonl` nằm sai thư mục con `logging/`, giá trị timestamp bị null |

### Cách xác minh

```bash
python main.py