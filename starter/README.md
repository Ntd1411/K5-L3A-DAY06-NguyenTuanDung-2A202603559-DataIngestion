# Starter · PostgreSQL + pgvector

Pipeline hoàn chỉnh cho corpus Sổ tay sinh viên: đọc PDF, chia chunk A/B/C, tạo embedding, lưu pgvector, tìm top-3 và tính Hit@1/Evidence Hit@3.

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf và python-dotenv
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # đọc và chuẩn hóa PDF
│   ├── chunking.py        # fixed-size và structure-aware chunking
│   ├── embeddings.py      # Voyage/OpenRouter/OpenAI/Gemini/local
│   ├── store.py           # lưu vector, metadata và filter
│   ├── evaluation.py      # chấm retrieval và lưu trace
│   └── run.py             # CLI chạy toàn pipeline
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
└── results/               # lưu kết quả của bạn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Thí nghiệm đã chạy với Voyage AI. Điền vào `.env` và **không commit API key**:

```env
VOYAGE_API_KEY=<your-key>
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-4
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=16
EMBEDDING_MIN_REQUEST_INTERVAL=31
```

Khoảng nghỉ 31 giây phù hợp tài khoản thử nghiệm có rate limit thấp; có thể giảm nếu tài khoản có hạn mức cao hơn. Giữ cùng model và số chiều cho A/B/C.

## 3. Chạy pipeline

Corpus nằm tại `data/so-tay-sinh-vien.pdf`, metadata tại `data/page_metadata.json` và benchmark tại `../benchmark/questions.json`.

Kiểm tra ingestion/chunking mà không gọi API:

```bash
python -m src.run --prepare-only --page-metadata data/page_metadata.json
```

Chạy đầy đủ:

```bash
python -m src.run --page-metadata data/page_metadata.json
```

Chạy unit test:

```bash
python -m unittest discover -s tests -v
```

Output chính: `results/ingestion_stats.json`, `results/retrieval_traces.json`, `results/summary.json` và `results/manual_audit.md`. Embedding cache không được commit và có thể tạo lại.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.
