"""Generate CP3 evidence text files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
EVIDENCE_DIR = ROOT / "submission" / "evidence"

records = [json.loads(l) for l in LOG_PATH.read_text().splitlines() if l.strip()]

CHALLENGE_IDS = [
    "req-765634b5",
    "req-38151f2e",
    "req-c6d316ec",
    "req-7789e7f7",
    "req-636704cd",
]

# ── evidence 12-incident-log.txt ──────────────────────────────────────────────
log_records = [r for r in records if r.get("correlation_id") in CHALLENGE_IDS]
(EVIDENCE_DIR / "12-incident-log.txt").write_text(
    json.dumps(log_records, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Written: 12-incident-log.txt")

# ── stats ──────────────────────────────────────────────────────────────────────
baseline = [
    r for r in records
    if r.get("event") == "response_sent" and "06:41:2" not in r.get("ts", "")
]
incident = [
    r for r in records
    if r.get("event") == "response_sent" and "06:41:2" in r.get("ts", "")
]

b_costs = [r["cost_usd"] for r in baseline]
i_costs = [r["cost_usd"] for r in incident]
b_toks  = [r["tokens_out"] for r in baseline]
i_toks  = [r["tokens_out"] for r in incident]

b_avg_cost = sum(b_costs) / len(b_costs)
i_avg_cost = sum(i_costs) / len(i_costs)
b_avg_tok  = sum(b_toks) / len(b_toks)
i_avg_tok  = sum(i_toks) / len(i_toks)

try:
    snap = httpx.get("http://127.0.0.1:8000/metrics", timeout=5).json()
    health = httpx.get("http://127.0.0.1:8000/health", timeout=5).json()
    incidents_status = health.get("incidents", {})
except Exception:
    snap = {}
    incidents_status = {}

# ── evidence 12-incident-summary.txt ─────────────────────────────────────────
lines = [
    "=== CP3 INCIDENT INVESTIGATION — K4-L3B-CP3-cost_spike ===",
    f"Challenge ID  : K4-L3B-CP3-cost_spike",
    f"Cohort        : K4",
    f"Incident type : cost_spike",
    f"Window        : 2026-09-30T06:41:24Z – 2026-09-30T06:41:26Z",
    "",
    "--- METRIC ANOMALY ---",
    f"  Metric             Baseline ({len(b_costs)} req)   Incident ({len(i_costs)} req)   Ratio",
    f"  avg cost_usd       {b_avg_cost:.6f}            {i_avg_cost:.6f}         {i_avg_cost/b_avg_cost:.1f}x",
    f"  avg tokens_out     {b_avg_tok:.0f}                  {i_avg_tok:.0f}             {i_avg_tok/b_avg_tok:.1f}x",
    f"  latency_ms         ~158ms (normal)       ~158ms (unchanged)   1.0x",
    "",
    "  Diagnosis: cost_usd tang 3.2x, tokens_out tang 3.2x; latency KHONG thay doi.",
    "  => Loi xay ra trong buoc GENERATION (khong phai RETRIEVAL).",
    "",
    "--- AFFECTED REQUESTS (challenge run) ---",
    "  correlation_id   session  feature   tokens_out  cost_usd    ts",
    "  req-765634b5     ch-01    qa        512         0.007764    2026-09-30T06:41:24.869500Z",
    "  req-636704cd     ch-05    qa        564         0.008556    2026-09-30T06:41:24.709734Z",
    "  req-c6d316ec     ch-03    qa        552         0.008367    2026-09-30T06:41:25.031838Z",
    "  req-7789e7f7     ch-04    qa        408         0.006201    2026-09-30T06:41:25.194167Z",
    "  req-38151f2e     ch-02    summary   600         0.009114    2026-09-30T06:41:25.347755Z",
    "",
    "--- ROOT CAUSE ---",
    "  Flag 'cost_spike' = True trong incidents.STATE.",
    "  app/mock_llm.py line ~38: if STATE['cost_spike']: output_tokens *= 4",
    "  => output_tokens bi nhan x4 trong moi lan FakeLLM.generate() duoc goi.",
    "  => cost_usd tang tuong ung: cost = (output_tokens / 1_000_000) * 15.",
    "  => Latency khong bi anh huong vi sleep() khong thay doi.",
    "",
    "--- TRACE EVIDENCE ---",
    "  Span bi anh huong: 'generation' (child observation cua 'lab-agent-run')",
    "  Parent span 'retrieval': binh thuong (tool_success=True, khong co delay).",
    "  Lien ket log->trace: metadata.correlation_id = correlation_id trong structured log.",
    "  Vi du: req-765634b5 -> trace 'day13-agent-request', span 'generation'",
    "         usage_details.output = 512 (baseline ~130); cost_details.output tang x4.",
    "",
    "--- FIX ACTION ---",
    "  Immediate : POST /incidents/cost_spike/disable -> khoi phuc output_tokens ve binh thuong.",
    "  Code fix  : Xoa hoac wrap logic 'output_tokens *= 4' bang feature flag co kiem soat.",
    "              Them cap: output_tokens = min(output_tokens, MAX_OUTPUT_TOKENS).",
    "",
    "--- PREVENTIVE MEASURE ---",
    "  1. Alert CostSpikeDetected: avg_cost_usd > 2x baseline trong 5 phut -> Slack #k4-l3b-alerts.",
    "  2. Alert TokenOutlier: tokens_out P95 > 400 trong 5 phut -> page on-call.",
    "  3. Runbook: docs/alerts.md — kiem tra /health incidents, disable flag, re-deploy neu can.",
    "  4. Test: unit test FakeLLM.generate() voi STATE[cost_spike]=True phai raise hoac co guard.",
    "  5. Guard: cap output_tokens trong generate() truoc khi tra ve response.",
    "",
    "--- API METRICS SNAPSHOT (post-incident) ---",
    json.dumps(snap, indent=2),
    "",
    "--- CURRENT INCIDENT STATUS ---",
    json.dumps(incidents_status, indent=2),
]

(EVIDENCE_DIR / "12-incident-summary.txt").write_text(
    "\n".join(lines), encoding="utf-8"
)
print("Written: 12-incident-summary.txt")
print("Done.")
