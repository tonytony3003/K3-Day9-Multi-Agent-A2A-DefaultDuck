# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Phí Đình Hoàng Anh  |
| MSSV            | 2A202601853       |
| Khóa/Lớp        | K3         |
| Vai trò chính   | Xây dựng pipeline và kiểm thử dữ liệu | 
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái                            |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Triển khai pipeline xử lý case | `process_cases.py` | `input/EC_*.json`, `data/*.csv` | `output/EC_*.json`, `logging/trace.jsonl` | Hoàn thành |
| Xây dựng tài liệu kiến trúc agent | `architecture.md` | Yêu cầu assignment | Mô tả luồng handoff | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Xây dựng logic rule-based và kiểm thử | Toàn bộ pipeline | Script chạy đúng với dữ liệu Olist hiện có | Traces và metadata |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Tạo pipeline xử lý case | `process_cases.py` | Script tạo output JSON theo schema | `python process_cases.py` |
| Chuẩn bị tài liệu kiến trúc | `architecture.md` | Mô tả rõ vai trò agent và luồng handoff | Xem file architecture.md |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Tạo `output/EC_*.json` theo schema bài tập và `logging/trace.jsonl` cho mỗi case.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Xây dựng mô-đun xử lý case tự động, từ đọc input JSON, join dữ liệu Olist, phân tích trạng thái order, đối soát payment, đến quyết định chính sách và xuất JSON đầu ra.

### Cách triển khai

Pipeline sử dụng quy tắc xác định issue theo thứ tự ưu tiên trong đề bài. `OrderSellerAgent` tính tổng giá trị item/freight và xác định seller muộn. `PaymentAgent` kiểm tra split payment và khớp tổng thanh toán với tổng chi phí. `PolicyAgent` quyết định refund và action dựa trên trạng thái order và các điều kiện đã cho. Kết quả được validate sơ bộ bởi `VerifierAgent`.

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | `input/EC_*.json`, `data/*.csv`        |
| Output                  | `output/EC_*.json`, `logging/trace.jsonl`, `metadata.json` |
| Module phụ thuộc        | `process_cases.py`, `DataLoader`, `PolicyAgent` |
| Module sử dụng output   | Người chấm, hệ thống score output | 
| Điều kiện lỗi cần xử lý | Missing order, thiếu file input, payment mismatch |

### Cách xác minh

```bash
python process_cases.py
```

- **Kết quả mong đợi:** Tạo các file JSON trong `output/` và ghi trace vào `logging/trace.jsonl`.
- **Kết quả thực tế:** Nếu chưa có file `EC_*.json` trong `input/`, script sẽ ghi trace trạng thái `no_cases_found`.
- **Artifact/log:** `logging/trace.jsonl`, `logging/metadata.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Quyết định sử dụng pipeline rule-based thay vì phụ thuộc LLM, vì đề bài yêu cầu luật nghiệp vụ rõ ràng và cần đầu ra tiêu chuẩn JSON.
- **Các phương án đã cân nhắc:** Sử dụng LLM để suy diễn và sinh output tự do; xây dựng pipeline deterministic bằng Python.
- **Phương án đã chọn:** Chọn pipeline deterministic rule-based.
- **Lý do:** Phương án rule-based cho phép kiểm soát chính xác điều kiện order/item/payment và dễ xác minh, đánh đổi bằng ít linh hoạt hơn so với LLM.
- **Bằng chứng quyết định phù hợp:** Artifact: `process_cases.py` và `logging/metadata.json`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Không có file input case chính thức nên không sinh được output JSON.
- **Lệnh hoặc bước tái hiện:** `python process_cases.py`
- **Nguyên nhân gốc:** Thư mục `input/` chỉ chứa `.gitkeep`; tập tin `EC_001.json`..`EC_050.json` chưa được cung cấp.
- **Cách xử lý:** Tạo `process_cases.py`, `architecture.md`, `logging/metadata.json`, `logging/trace.jsonl` để chuẩn bị sẵn pipeline và định dạng output.
- **Cách xác minh sau khi sửa:** `python process_cases.py` -> trace `no_cases_found` nếu không có input case JSON.
- **Điều học được:** Luôn kiểm tra đầu vào trước khi chạy pipeline; tách biệt rõ agent dữ liệu và agent chính sách giúp dễ bảo trì.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu Olist được đọc vào bằng `DataLoader` từ các file CSV, sau đó gộp theo `claimed_order_id` từ case input.
2. Evaluation set là các case `EC_*.json`, và ground-truth được suy luận từ quy tắc nghiệp vụ trong đề bài.
3. Quality checks đảm bảo schema JSON, giá trị issue hợp lệ và tổng refund được làm tròn chính xác; khác với freshness monitoring ở chỗ quality checks tập trung vào correctness của output.
4. Dùng cùng test set để giữ benchmark nhất quán giữa các phiên bản và đảm bảo toàn bộ case được so sánh theo cùng thang điểm.
5. Repair được xem là thành công khi `output/EC_*.json` có cấu trúc đúng, trace được ghi lại đầy đủ, và `metadata.json` mô tả runtime.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo của thành viên khác.

**Họ và tên:** Phí Đình Hoàng Anh
**Ngày xác nhận:** 2026-08-05
