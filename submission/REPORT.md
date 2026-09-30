# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Lê Phước Tiến
- **MSSV:** 2A202602616
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-02616`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log (text) | `evidence/12-incident-log.txt` |
| Incident log (ảnh) | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | Chưa đạt CP1 | 100/100 | Đủ schema, context, correlation ID và PII scrub |
| `validate_dashboard.py` | Chưa hoàn thiện | 6/6 panel | Contract hợp lệ |
| `pytest` | Starter | 28 passed | Có thêm test PII, correlation ID và generation metadata |
| Số traces hợp lệ | 0 trace đủ cây | 13 | Xác minh bằng Observations API v2 |
| Số PII leak | Có nguy cơ PII thô | 0 | Validator quét email, phone, CCCD và thẻ |
| Latency P95 / TTFT P95 | N/A | 1163 ms / 55 ms | Baseline 20 response thành công |
| Retrieval success rate | N/A | 100% | Tính trên mọi event có `tool_success` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware nhận `x-request-id`, nếu thiếu thì sinh `req-<8-hex>`, bind vào context, truyền vào agent/trace và trả lại qua response header.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, latency, TTFT, token, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` chạy sau khi format exception nhưng trước khi ghi JSONL/render JSON; processor duyệt đệ quy string trong dict/list.
- **Cách kiểm chứng kết quả:** 28 tests pass và `validate_logs.py` đạt 100/100, không phát hiện PII thô. Evidence structured log dùng `correlation_id=req-04c0ffee`; evidence PII dùng `correlation_id=req-05deadbe`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy workload local với session ID riêng rồi dùng Langfuse Observations API v2 kiểm tra 13 trace trong project `day13-k4-l3b-02616`.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` loại agent có hai child cùng `parent_observation_id`: `retrieval` loại retriever và `generation` loại generation. Cả ba đều tắt capture raw input/output.
- **Cách nối trace với log:** Metadata trace và generation chứa cùng `correlation_id` với structured log; ví dụ rollback `req-4d218507` tương ứng trace `db8a69cc1a09e811cd3f913b24818763`.
- **Prompt name:** `day13-chat` (text prompt, giữ `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** v1 — `baseline`, trạng thái cuối có thêm `production`.
- **Version/label candidate:** v2 — `candidate`.
- **Trace ID của mỗi version:** v1 baseline `3b0a8956b5ec08b00cb20b42cf828256`; v2 candidate `f026026d8af3bcba9d85258e13134a55`.
- **Cách promote và rollback `production`:** Promote `production` sang v2 và xác minh trace `f533489e9f472b99894d018de1c607ac`; sau đó chuyển `production` về v1 và xác minh trace `db8a69cc1a09e811cd3f913b24818763`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard runtime tại `evidence/11-dashboard-overview.png` đọc `data/logs.jsonl`, hiển thị Latency/TTFT, Traffic, Errors/Retrieval, Cost, Tokens và Quality trong 60 phút, refresh 30 giây và có threshold.
- **SLO và lý do chọn:** 99,5% request trong 28 ngày phải thành công và có latency không quá 3000 ms. Baseline P95 1163 ms nên ngưỡng có khoảng đệm vận hành nhưng vẫn phát hiện suy giảm rõ.
- **Cách tính error budget:** `10.000 × (1 - 0,995) = 50`; tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms trong cửa sổ.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms/5m), `HighRequestErrorRate` (>2%/5m), `LowRetrievalSuccessRate` (<90%/10m); cả ba gửi Slack `#k4-l3b-alerts`, owner `student-2A202602616`, runbook tại `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** `2026-09-30T08:42:32Z – 2026-09-30T08:42:45Z`
- **Triệu chứng từ metrics:** Dashboard Latency panel cho thấy `latency_ms` tăng đột biến từ baseline ~160 ms lên ~2665 ms (tăng **16.7×**, vượt `latency_threshold_ms=2000` trong challenge). TTFT không thay đổi (~55 ms), cost bình thường (~0.0022 USD), error rate = 0%. Anomaly chỉ xuất hiện ở latency — dấu hiệu điển hình của bottleneck tại bước retrieval. Evidence tại `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** Event `response_sent` của `correlation_id=req-739e800f` (session `k4-l3b-challenge-s03`, feature `monitoring`) ghi `latency_ms=2656`, `tool_name=retrieval`, `tool_success=true` lúc `2026-09-30T08:42:35.077843Z`. Toàn bộ 5 corr ID: `req-739e800f`, `req-ac6a94fb`, `req-44802f84`, `req-c2267e74`, `req-ec11af68`. Evidence đầy đủ tại `evidence/12-incident-log.txt` và `evidence/13-incident-log.png`.
- **Trace ID và span gây ảnh hưởng:** Span `retrieval` (child observation của root `lab-agent-run`, trace name `day13-agent-request`) bị ảnh hưởng — duration ~2500 ms bất thường. Span `generation` bình thường: TTFT 52–55 ms, tokens và cost không thay đổi. Nối log→trace qua `metadata.correlation_id` = `correlation_id` trong structured log (ví dụ `req-739e800f` → trace trong project `day13-k4-l3b-02616`). Evidence tại `evidence/14-incident-trace.png`.
- **Root cause:** Flag `rag_slow = True` trong `incidents.STATE`. Code tại `app/mock_rag.py`: `if STATE["rag_slow"]: time.sleep(2.5)` — hàm `retrieve()` sleep 2.5 giây trước khi trả docs. Latency cuối = 2500 ms sleep + ~160 ms xử lý bình thường = ~2660 ms. TTFT và cost không bị ảnh hưởng vì LLM `generate()` hoạt động bình thường sau khi nhận được docs.
- **Fix action:** Immediate — `POST /incidents/rag_slow/disable` để tắt flag và khôi phục `retrieve()` về bình thường ngay lập tức. Code fix lâu dài: xoá `time.sleep(2.5)` trong `mock_rag.py`; production: thêm timeout và circuit breaker cho vector store calls để fail fast thay vì hang.
- **Preventive measure:** (1) Alert `HighLatencyP95`: `latency_ms P95 > 2000 ms` trong 5 phút → Slack `#k4-l3b-alerts`. (2) Alert `RetrievalSlowdown`: retrieval span duration P95 > 1000 ms trong 5 phút → page on-call. (3) Runbook tại `docs/alerts.md`: kiểm tra `GET /health` → `incidents`, gọi `/disable`, verify latency trở về baseline. (4) Timeout: thêm `timeout=1.0s` cho `retrieve()` để fail fast. (5) Circuit breaker: sau 3 lần chậm liên tiếp, fallback về general answer không dùng RAG. (6) SLO gate trong CI: load test phải pass `latency_ms P95 < 500 ms`.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Đặt PII processor trước JSON renderer trong structlog pipeline để đảm bảo scrubbing xảy ra trước khi bất kỳ serializer nào ghi dữ liệu ra file — không thể bypass dù log path thay đổi.
- **Một lỗi/blocker đã gặp:** Conflict khi pull origin do template REPORT.md được cập nhật cùng lúc với bài làm.
- **Cách tìm nguyên nhân và xử lý:** Đọc conflict markers, giữ phần bài làm thực tế (stashed changes), merge với template mới từ upstream.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metric (Latency panel) phát hiện anomaly → filter log theo correlation_id trong khoảng thời gian → tìm trace cùng correlation_id trong Langfuse → khoanh vùng span bất thường (`retrieval` duration 2500 ms) → kết luận root cause.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version cho phép A/B test và rollback an toàn khi candidate gây regression. Token/cost monitoring phát hiện cost_spike trước khi bill tăng. SLO + error budget giúp prioritize alert: chỉ page on-call khi budget bị tiêu quá ngưỡng.
- **Điều quan trọng nhất đã học:** Ba signal (metric, log, trace) phải cùng chỉ về một nguyên nhân mới đủ để kết luận root cause — không thể dùng một signal duy nhất.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Ảnh 13-incident-log và 14-incident-trace là screenshot từ terminal và Langfuse; không thể tự động hóa bước chụp browser.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
