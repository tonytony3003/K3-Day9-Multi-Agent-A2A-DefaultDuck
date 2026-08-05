# Flow chạy và xuất output

## 1. Thành phần còn cần trước khi chạy

- Python 3.11 trở lên.
- `.env` có `OPENROUTER_API_KEY` và `OPENROUTER_MODEL=openai/gpt-4o-mini` nếu chạy chế độ LLM.
- 50 input JSON trong `input/` và 9 CSV trong `data/`.
- Cài dependency bằng `python -m pip install -r requirements.txt`.

Các biến Voyage không được pipeline Day 9 sử dụng vì bài toán không cần embedding hoặc retrieval.

## 2. Flow thực thi

```text
preflight input/data
  -> Coordinator
  -> [OrderSeller || Payment || Delivery]
  -> deterministic EC_POLICY_V1 engine
  -> Policy Agent
  -> independent Verifier
  -> atomic output writer
  -> submission audit
  -> logging/trace.jsonl + logging/metadata.json
```

Ba specialist là ba node song song trong LangGraph. Mỗi node chỉ nhận view dữ liệu thuộc domain của mình. Policy engine và Verifier đều tái tính từ CSV; output chỉ được ghi khi validation pass.

## 3. Chạy kiểm thử

```powershell
python -m pytest -q
```

## 4. Sinh output không gọi API

Chế độ này dùng đầy đủ graph, handoff, policy và verifier nhưng không gọi model. Phù hợp để debug và kiểm tra tài chính:

```powershell
python -m src.main --mode deterministic
```

Chạy một case:

```powershell
python -m src.main --mode deterministic --case EC_001
```

## 5. Chạy multi-agent với GPT-4o mini

Lệnh sau gọi riêng Coordinator, ba specialist, Policy và Verifier cho mỗi case. Với 50 case bình thường sẽ tạo khoảng 300 API calls:

```powershell
python -m src.main --mode llm
```

Runner hiển thị progress bar `tqdm` theo số case, elapsed time, tốc độ và ETA. Ví dụ:

```text
Processing (llm):  40%|████        | 20/50 [03:12<04:48, 9.60s/case, EC_020]
```

Tắt progress bar khi chạy CI hoặc redirect log:

```powershell
python -m src.main --mode llm --no-progress
```

Nên smoke-test một case trước để kiểm tra OpenRouter structured output và quota:

```powershell
python -m src.main --mode llm --case EC_001
```

Runner kiểm tra credential qua endpoint `/api/v1/key` trước khi đọc/chuyển dữ liệu case. Nếu nhận `401`, tạo key mới tại OpenRouter Settings → Keys, thay đúng dòng sau trong `.env`, rồi mở terminal mới hoặc chạy lại lệnh:

```dotenv
OPENROUTER_API_KEY=sk-or-v1-...
```

## 6. Artifact sau khi chạy

- `output/EC_001.json` đến `output/EC_050.json`.
- `logging/trace.jsonl`: trace của lần chạy mới nhất, tự truncate khi bắt đầu.
- `logging/metadata.json`: model, framework, runtime, execution mode và aggregate audit.

Chỉ zip 50 file JSON trong `output/`; không đưa `.env`, source, trace hoặc metadata vào file submission zip.
