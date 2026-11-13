# Đánh giá thủ công

## Phương pháp

- **Tính mạch lạc:** dùng cùng 10 vị trí nguồn là đoạn bằng chứng của q01–q10 cho A, B và C. Đọc đoạn chứa vị trí đó và chấm 0–2: 0 = bị cắt làm mất ý; 1 = hiểu được một phần nhưng thiếu ngữ cảnh; 2 = tự hiểu được và giữ trọn ý. C dùng cùng đoạn với B nên nhận cùng nhãn.
- **Siêu dữ liệu:** đối chiếu 5 câu kiểm tra × ba kết quả đầu của từng cấu hình với PDF và `page_metadata.json`. Một bản ghi đạt khi đúng `document_id`, `source`, `page`, `section`, `language` và `document_type`.
- **Chất lượng thông tin nền:** đọc ba kết quả đầu của 5 câu kiểm tra cho từng cấu hình. Chấm 0 = không có bằng chứng; 1 = có bằng chứng nhưng thiếu điều kiện hoặc ngữ cảnh; 2 = đủ để trả lời và truy lại trang nguồn.

## Tính mạch lạc của chunk

| Vị trí | Trang | A | Lý do A | B/C | Lý do B/C |
|---|---:|---:|---|---:|---|
| q01 | 8 | 1 | Bắt đầu giữa từ và kết thúc giữa tiêu đề kế tiếp, dù định nghĩa tín chỉ còn đọc được. | 2 | Giữ trọn định nghĩa tín chỉ và phần giải thích liên quan. |
| q02 | 8 | 1 | Hai biên đều cắt giữa nội dung lân cận. | 2 | Có tiêu đề, phân loại và trọn định nghĩa học phần bắt buộc. |
| q03 | 8 | 2 | Ba trọng số và tiêu đề vẫn nằm trọn trong đoạn. | 2 | Giữ trọn mục đánh giá học phần và ba dấu đầu dòng. |
| q04 | 9 | 1 | Bắt đầu giữa bảng điểm nên ngữ cảnh bảng chưa hoàn chỉnh. | 2 | Có tiêu đề cách tính điểm, tiêu đề cột và dòng F. |
| q05 | 10 | 0 | Câu bị cắt tại “2 tuần tr”, làm mất điều kiện thời gian đầy đủ. | 2 | Giữ trọn mục 4.3 và mốc hai tuần. |
| q06 | 10 | 2 | Tiêu đề, tiêu đề cột và giá trị 10/25 đều có trong đoạn. | 2 | Giữ trọn mục 4.1 và bảng khối lượng học tập. |
| q07 | 11 | 2 | Giữ trọn thời hạn rút học phần và hậu quả quá hạn. | 2 | Tách đúng mục 4.5, ý hoàn chỉnh. |
| q08 | 11 | 1 | Bắt đầu giữa đoạn học cải thiện và trộn với tiêu đề mục tiếp theo. | 1 | Mục học lại rõ nhưng câu cuối bị cắt sau chữ “nếu”. |
| q09 | 11 | 2 | Có tiêu đề chương trình thứ hai và điều kiện thời điểm. | 1 | Có ý chính nhưng bắt đầu bằng phần dư mục trước và chỉ giữ một phần các điều kiện tiếp theo. |
| q10 | 12 | 2 | Điều kiện điểm trung bình và trường hợp giảm hạng còn trọn ý. | 2 | Giữ nguyên nhóm điều kiện xét tốt nghiệp. |
| **Trung bình** |  | **1,4/2** |  | **1,8/2** | C dùng cùng đoạn với B nên cùng điểm. |

## Kiểm tra siêu dữ liệu

| Cấu hình | Siêu dữ liệu đủ và đúng | Bộ lọc áp dụng | Tuân thủ bộ lọc |
|---|---:|---|---:|
| A | 15/15 | Không | Không áp dụng; ba kết quả đầu của q16–q17 tình cờ đúng phạm vi 2/2 |
| B | 15/15 | Không | Không áp dụng; q17 có một đoạn `overview` ngoài phạm vi |
| C | 15/15 | Có khi câu hỏi cung cấp bộ lọc | 2/2 câu kiểm tra; toàn bộ ba kết quả của mỗi câu đúng `section` |

Chi tiết đối chiếu; mỗi ô ghi `trang/section` theo thứ tự hạng 1–3:

| Cấu hình | Câu | Top-3 | Đúng trường bắt buộc | Tuân thủ phạm vi yêu cầu |
|---|---|---|---:|---|
| A | q16 | 24/party_and_union; 24/party_and_union; 24/party_and_union | 3/3 | Không áp dụng bộ lọc; cả 3 hit cùng phạm vi |
| A | q17 | 28/support_services; 28/support_services; 29/support_services | 3/3 | Không áp dụng bộ lọc; cả 3 hit cùng phạm vi |
| A | q18 | 30/support_services; 19/student_management; 29/support_services | 3/3 | Câu hỏi không có bộ lọc |
| A | q19 | 31/support_services; 31/support_services; 30/support_services | 3/3 | Câu hỏi không có bộ lọc |
| A | q20 | 7/overview; 32/support_services; 2/overview | 3/3 | Câu hỏi không có bộ lọc |
| B | q16 | 24/party_and_union; 24/party_and_union; 25/party_and_union | 3/3 | Không áp dụng bộ lọc; cả 3 hit cùng phạm vi |
| B | q17 | 28/support_services; 2/overview; 29/support_services | 3/3 | Không áp dụng bộ lọc; một hit ngoài phạm vi |
| B | q18 | 30/support_services; 19/student_management; 31/support_services | 3/3 | Câu hỏi không có bộ lọc |
| B | q19 | 31/support_services; 31/support_services; 33/support_services | 3/3 | Câu hỏi không có bộ lọc |
| B | q20 | 32/support_services; 7/overview; 2/overview | 3/3 | Câu hỏi không có bộ lọc |
| C | q16 | 24/party_and_union; 24/party_and_union; 25/party_and_union | 3/3 | Đạt; 3/3 hit đúng `party_and_union` |
| C | q17 | 28/support_services; 29/support_services; 29/support_services | 3/3 | Đạt; 3/3 hit đúng `support_services` |
| C | q18 | 30/support_services; 19/student_management; 31/support_services | 3/3 | Câu hỏi không có bộ lọc |
| C | q19 | 31/support_services; 31/support_services; 33/support_services | 3/3 | Câu hỏi không có bộ lọc |
| C | q20 | 32/support_services; 7/overview; 2/overview | 3/3 | Câu hỏi không có bộ lọc |

Không phát hiện bản ghi sai siêu dữ liệu trong 45 bản ghi được kiểm tra. `section` giúp loại đoạn mục lục ở q17, nhưng giá trị này được gán thủ công theo toàn trang nên có thể chưa đủ chi tiết với trang chứa nhiều chủ đề.

## Chất lượng thông tin nền

| Cấu hình | q16 | q17 | q18 | q19 | q20 | Phân bố 0/1/2 | Trung bình |
|---|---:|---:|---:|---:|---:|---|---:|
| A | 1 | 2 | 2 | 2 | 2 | 0/1/4 | 1,8/2 |
| B | 2 | 2 | 2 | 2 | 2 | 0/0/5 | 2,0/2 |
| C | 2 | 2 | 2 | 2 | 2 | 0/0/5 | 2,0/2 |

Lý do cho từng nhãn:

| Câu | A | B | C |
|---|---|---|---|
| q16 | **1:** ba kết quả đầu có các phần liên quan nhưng điều kiện “ĐẠT YÊU CẦU”, giấy chứng nhận và kết luận bị chia qua nhiều đoạn. | **2:** kết quả đầu giữ trọn điều kiện, giấy chứng nhận, kết luận và trang 24. | **2:** giống B, đồng thời cả ba kết quả đầu tuân thủ `party_and_union`. |
| q17 | **2:** kết quả đầu chứa đầy đủ giờ mở cửa các ngày trong tuần và trang 28. | **2:** kết quả đầu chứa đủ thời gian và trang nguồn; một kết quả khác thuộc mục lục nhưng không làm thiếu bằng chứng. | **2:** kết quả đầu đủ bằng chứng; bộ lọc loại kết quả mục lục khỏi ba kết quả đầu. |
| q18 | **2:** kết quả đầu chứa cả quy tắc thu hồi email và các trường hợp ngoại lệ ở trang 30. | **2:** kết quả đầu chứa đầy đủ quy tắc và ngoại lệ. | **2:** giống B; câu hỏi không yêu cầu bộ lọc. |
| q19 | **2:** kết quả đầu nêu rõ nộp bài để kiểm tra độ trùng lặp bằng Turnitin và có trang nguồn. | **2:** kết quả đầu giữ trọn mục “Nộp bài tập” và mục đích kiểm tra độ trùng lặp. | **2:** giống B; câu hỏi không yêu cầu bộ lọc. |
| q20 | **2:** kết quả đầu có URL tương đương ở trang 7 và kết quả thứ hai có đúng bằng chứng chuẩn ở trang 32. | **2:** kết quả đầu có URL, hướng dẫn truy cập và trang 32. | **2:** giống B; câu hỏi không yêu cầu bộ lọc. |
