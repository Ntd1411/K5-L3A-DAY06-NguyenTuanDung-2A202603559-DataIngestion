# Báo cáo cá nhân — Day 6

## Dữ liệu và quy trình xử lý

- **Chủ đề:** Quy định đào tạo, quản lý sinh viên và dịch vụ hỗ trợ trong *Sổ tay sinh viên 2021* của Trường Đại học Kinh tế Quốc dân.
- **Quy mô:** PDF có 33 trang vật lý. Tôi tính 30 trang nội dung gồm trang 3–21 và 23–33; loại trang 1 vì không có văn bản, trang 2 vì là mục lục, trang 22 vì chỉ có tiêu đề. Tổng nội dung chuẩn hóa của 30 trang là 33.213 ký tự. Để không loại bỏ âm thầm dữ liệu đã đọc được, quy trình vẫn tạo đoạn cho 32 trang có văn bản; vì vậy số đoạn bên dưới bao gồm cả trang 2 và 22, nhưng hai trang này không được tính vào yêu cầu 30 trang nội dung. Bản kê dữ liệu: [`data/manifest.json`](../../data/manifest.json).
- **Nguồn và quyền:** PDF được tải công khai từ [tên miền chính thức của NEU](https://neu.edu.vn/Resources/Docs/SubDomain/phongctctqlsv/S%E1%BB%95%20tay%20sinh%20vi%C3%AAn.pdf), truy cập ngày 13/11/2026. Bản công khai và file trong repo trùng khớp hoàn toàn ở cấp byte với SHA-256 `6786bba2e82fb8cd5972795c0499cebf33e51d534ad7b505586e07430c240348`. Siêu dữ liệu PDF ghi tiêu đề *Sổ tay sinh viên 2021*, tác giả “Hương Nguyễn Thu”, ngày tạo 31/08/2021. PDF không nêu giấy phép tái phân phối rõ ràng; tôi giữ nguyên thông tin nguồn và không suy đoán thêm quyền sử dụng.
- **Đọc và chuẩn hóa:** Dùng `pypdf`, chuẩn hóa Unicode NFKC, CRLF, khoảng trắng ngang và giữ ranh giới dòng/đoạn. Có 32/33 trang trích xuất được văn bản; trang 1 không có văn bản. Không dùng OCR. Hạn chế chính là bố cục nhiều cột và bảng làm sai thứ tự văn bản, đồng thời một số dấu tiếng Việt chưa được trích xuất chính xác.
- **Mô hình biểu diễn và lưu trữ vector:** Dùng Voyage AI `voyage-4`, vector 1.024 chiều; tài liệu và câu hỏi được gửi với `input_type` tương ứng là `document` và `query`. Hệ lưu trữ gồm PostgreSQL 16.16 và pgvector 0.8.7, sử dụng độ tương đồng cosine và tìm kiếm vector chính xác. Vector được lưu bền vững trong bảng theo số chiều; thao tác chèn hoặc cập nhật dùng khóa `(strategy, chunk_id)` và thay các đoạn cũ của cùng tài liệu để tránh nhân đôi.
- **Chi phí và thời gian:** Không ghi nhận chi phí API vì lượt chạy nằm trong hạn mức miễn phí; chưa đối chiếu hóa đơn từ trang quản trị của nhà cung cấp. `summary.json` ghi lượt chạy lại sử dụng toàn bộ bộ nhớ đệm: 6,4437 giây và không phát sinh yêu cầu API. Thời gian của lượt chạy đầu tiên chưa được lưu thành tệp kết quả độc lập, vì vậy không dùng số thời gian hiện tại để so sánh tốc độ giữa các cấu hình.
- **Lệnh chạy:** `cd starter && source .venv/bin/activate && python -m src.run --page-metadata data/page_metadata.json`.
- **Siêu dữ liệu:** Mỗi đoạn có `document_id`, `source`, `page`, `section`, `language`, `document_type`, trạng thái trích xuất và chỉ số đoạn. `section` được gán thủ công theo tiêu đề và trang trong [`page_metadata.json`](../../starter/data/page_metadata.json), dùng để lọc phạm vi. Không thêm `year` hoặc `version` vì nguồn không cung cấp cấu trúc phiên bản đủ tin cậy ngoài tiêu đề tài liệu.

## Cấu hình và bộ đánh giá

| Cấu hình | Cách chia đoạn | Siêu dữ liệu/bộ lọc | Số chunk |
|---|---|---|---:|
| A | Cửa sổ cố định 500 ký tự, chồng lấn 50 ký tự | Có siêu dữ liệu, không lọc | 89 |
| B | Nhận diện tiêu đề, dấu đầu dòng và đoạn; tối đa 800 ký tự | Cùng siêu dữ liệu, không lọc | 65 |
| C | Giống hệt B | Chỉ lọc `section` khi câu hỏi cung cấp bộ lọc | 65 |

A–B chỉ thay cách chia đoạn; B–C chỉ thay bộ lọc siêu dữ liệu. Tập tài liệu, câu hỏi, mô hình biểu diễn, cơ sở dữ liệu vector và độ tương đồng cosine được giữ nguyên.

Bộ đánh giá có 20 câu trong [`benchmark/questions.json`](../../benchmark/questions.json): 15 câu phát triển (`dev`) và 5 câu kiểm tra (`test`); gồm câu trực tiếp, diễn đạt lại, điều kiện, ngoại lệ và 4 câu có bộ lọc siêu dữ liệu (q05, q13, q16, q17; trong tập kiểm tra có q16 và q17). Mỗi câu có đáp án, nguồn, trang và đoạn bằng chứng. Bằng chứng được kiểm tra là có trên đúng trang và nằm trọn trong ít nhất một đoạn của B/C trước lượt đánh giá cuối.

Tiêu chí chọn là ưu tiên Evidence Hit@3, sau đó là chất lượng thông tin nền, tính mạch lạc và khả năng giới hạn phạm vi bằng siêu dữ liệu. Kho mã nguồn chưa có nhật ký thời gian riêng để chứng minh tiêu chí này được chốt trước khi xem tập kiểm tra; đây là một hạn chế của quy trình.

## Kết quả truy xuất

| Cấu hình | Tập | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Số chunk | Thời gian | Chi phí |
|---|---|---:|---:|---:|---|---|
| A | Phát triển | 13/15 | 14/15 | 89 | Dùng chung lượt chạy | Không ghi nhận chi phí |
| A | Kiểm tra | 3/5 | 4/5 | 89 | Dùng chung lượt chạy | Không ghi nhận chi phí |
| B | Phát triển | 15/15 | 15/15 | 65 | Dùng chung lượt chạy | Không ghi nhận chi phí |
| B | Kiểm tra | 5/5 | 5/5 | 65 | Dùng chung lượt chạy | Không ghi nhận chi phí |
| C | Phát triển | 15/15 | 15/15 | 65 | Dùng chung lượt chạy | Không ghi nhận chi phí |
| C | Kiểm tra | 5/5 | 5/5 | 65 | 6,4437 giây cho toàn quy trình có bộ nhớ đệm | Không ghi nhận chi phí |

Dấu vết truy xuất đầy đủ: [`retrieval_traces.json`](../../starter/results/retrieval_traces.json). Tệp tổng hợp: [`summary.json`](../../starter/results/summary.json).

## Đánh giá thủ công

| Cấu hình | Mạch lạc TB /2 (n=10) | Siêu dữ liệu đủ và đúng | Tuân thủ bộ lọc | Thông tin nền 0/1/2 và TB /2 |
|---|---:|---:|---|---|
| A | 1,4 | 15/15 | Không áp dụng | 0/1/4; 1,8 |
| B | 1,8 | 15/15 | Không áp dụng | 0/0/5; 2,0 |
| C | 1,8 | 15/15 | 2/2 câu test | 0/0/5; 2,0 |

Chi tiết từng nhãn và lý do: [`manual_audit.md`](../../starter/results/manual_audit.md).

## Phân tích và kết luận

### A so với B

Trên tập tài liệu và bộ câu hỏi của thí nghiệm, B đạt kết quả cao hơn A: ít hơn 24 đoạn nhưng điểm mạch lạc tăng từ 1,4 lên 1,8; Hit@1 trên tập kiểm tra tăng từ 3/5 lên 5/5 và Evidence Hit@3 tăng từ 4/5 lên 5/5. Nguyên nhân chính là cách chia theo tiêu đề và dấu đầu dòng giữ điều kiện và kết luận trong cùng đoạn.

- **q05, trang 10:** A cắt câu tại “2 tuần tr”, nên không đoạn nào chứa đủ bằng chứng “2 tuần trước thời điểm bắt đầu học kỳ”; câu hỏi không đạt Evidence Hit@3. B giữ trọn mục 4.3.
- **q16, trang 24:** A chia điều kiện “ĐẠT YÊU CẦU”, giấy chứng nhận và kết luận tiên quyết qua các đoạn khác nhau; câu hỏi không đạt Evidence Hit@3 và chất lượng thông tin nền được chấm 1. B giữ bằng chứng trong một đoạn.
- **q20:** A xếp trang 7 ở hạng 1 vì có URL tương đương, trong khi bằng chứng chuẩn ở trang 32 xuất hiện hạng 2. Chỉ số so khớp chính xác với bằng chứng chuẩn ghi Hit@1 không đạt dù kết quả hạng 1 vẫn có thể trả lời câu hỏi; đây là hạn chế khi chỉ khai báo một nguồn bằng chứng chuẩn.

### B so với C

B và C có cùng Hit@1/Hit@3 vì hai câu kiểm tra có bộ lọc vốn đã truy xuất đúng bằng chứng. Tuy nhiên, q17 cho thấy giá trị của bộ lọc: B đưa một đoạn thuộc `overview` vào ba kết quả đầu, còn C giới hạn cả ba kết quả trong `support_services`. C tuân thủ bộ lọc ở 2/2 câu kiểm tra. Đổi lại, C chỉ dùng được khi bộ lọc là đầu vào đáng tin cậy; không được suy ra `section` từ đáp án chuẩn.

### Lựa chọn

Tôi chọn **C** cho tập tài liệu này vì giữ chất lượng chunk của B và có thể loại kết quả ngoài phạm vi khi câu hỏi cung cấp `section`. Nếu không có siêu dữ liệu hoặc bộ lọc đáng tin cậy, B là lựa chọn tương đương và đơn giản hơn.

### Hạn chế và hướng cải tiến

- Chỉ có một tài liệu và 5 câu kiểm tra nên không thể kết luận cấu hình tốt nhất nói chung.
- Siêu dữ liệu `section` được gán theo trang; trang có nhiều chủ đề có thể cần siêu dữ liệu theo khối nội dung hoặc tiêu đề.
- Cách so khớp chính xác bằng chứng làm q20 bị đánh giá thấp dù có bằng chứng tương đương ở trang khác; lần sau cần khai báo nhiều nguồn chuẩn hợp lệ.
- PDF có lỗi bố cục; nên thử công cụ phân tích PDF có khả năng giữ bố cục hoặc OCR có kiểm chứng.
- Nhãn đánh giá thủ công chưa được người chấm thứ hai đánh giá độc lập.
- Thời gian lượt chạy đầu và lượt chạy có bộ nhớ đệm chưa được lưu trong cùng một cấu trúc; lần sau cần ghi riêng từng lượt chạy, số token và chi phí trực tiếp từ nhà cung cấp.
- Nguồn công khai đã được xác minh bằng mã băm, nhưng PDF không nêu giấy phép tái phân phối; nếu kho mã nguồn bắt buộc công khai thì cần xác nhận thêm với giảng viên hoặc chủ sở hữu, hoặc chỉ nộp bản kê dữ liệu và hướng dẫn tải.

Nếu mở rộng, tôi sẽ thêm tài liệu thuộc nhiều năm hoặc phiên bản, tăng kích thước tập kiểm tra độc lập, gán `section` theo tiêu đề thay vì toàn trang và thử truy xuất kết hợp vector với BM25 trên cùng bộ đánh giá.
