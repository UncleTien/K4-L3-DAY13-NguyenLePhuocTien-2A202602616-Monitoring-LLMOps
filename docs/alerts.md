# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 của `response_sent.latency_ms`; SLO request thành công trong 3000 ms.
- Điều kiện và thời gian duy trì: P95 latency lớn hơn 3000 ms liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn ngưỡng SLO để nhận câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency, xác nhận P95/P99, TTFT và khoảng thời gian vượt ngưỡng.
  2. Lọc `response_sent` trong khoảng đó, chọn request có `latency_ms` cao và lấy `correlation_id`.
  3. Mở trace cùng `correlation_id`, so sánh thời gian của `retrieval` và `generation`.
- Mitigation tạm thời: tắt scenario gây chậm hoặc rollback prompt/config gần nhất; giảm tải nếu cả hai span đều chậm.
- Owner: `student-2A202602616`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỉ lệ `request_failed` trên `request_received`; SLO 99,5% request tốt.
- Điều kiện và thời gian duy trì: error rate lớn hơn 2% liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: request trả lỗi và không cung cấp được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xác nhận error rate, loại lỗi và khoảng thời gian tăng.
  2. Lọc `request_failed`, nhóm theo `error_type`, rồi lấy một `correlation_id` đại diện.
  3. Mở trace cùng `correlation_id`, tìm child observation lỗi và status message liên quan.
- Mitigation tạm thời: tắt incident/practice scenario, rollback thay đổi gần nhất hoặc chuyển sang fallback khi dependency lỗi.
- Owner: `student-2A202602616`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỉ lệ `tool_success == true` trên mọi event có field `tool_success`.
- Điều kiện và thời gian duy trì: retrieval success thấp hơn 90% liên tục trong 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu context hoặc request thất bại khi truy xuất tài liệu.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xác nhận retrieval success và thời điểm bắt đầu giảm.
  2. Lọc mọi event có `tool_success`, chọn event false và lấy `correlation_id`.
  3. Mở trace cùng `correlation_id`, kiểm tra observation `retrieval` trước khi xem `generation`.
- Mitigation tạm thời: tắt scenario tool fail, kiểm tra vector store và dùng fallback không-RAG đã được phê duyệt trong lúc khôi phục.
- Owner: `student-2A202602616`
