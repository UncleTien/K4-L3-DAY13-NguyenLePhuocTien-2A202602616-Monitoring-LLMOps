"""Generate 11-dashboard-overview.png with 6 panels using PIL only."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
OUT = ROOT / "submission" / "evidence" / "11-dashboard-overview.png"

# ── palette ────────────────────────────────────────────────────────────────────
BG      = (8,  13,  24)
CARD_BG = (17, 24,  39)
CARD_BR = (41, 53,  72)
WHITE   = (229, 231, 235)
MUTED   = (148, 163, 184)
GRID    = (45,  55,  72)
ORANGE  = (251, 146, 60)
BLUE    = (56,  189, 248)
PURPLE  = (167, 139, 250)
GREEN   = (52,  211, 153)
YELLOW  = (251, 191, 36)
PINK    = (244, 114, 182)
RED     = (251, 113, 133)
LIME    = (163, 230, 53)

W, H = 1440, 1060


def load_records():
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        r["_ts"] = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        records.append(r)
    records.sort(key=lambda r: r["_ts"])
    latest = max(r["_ts"] for r in records)
    start  = latest - timedelta(minutes=60)
    window = [r for r in records if r["_ts"] >= start]
    return window, start, latest


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = (len(s) - 1) * p / 100
    lo, hi = math.floor(idx), math.ceil(idx)
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (idx - lo)


def by_minute(records, event, field, agg="mean"):
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for r in records:
        if r.get("event") == event and isinstance(r.get(field), (int, float)):
            m = r["_ts"].replace(second=0, microsecond=0)
            buckets[m].append(float(r[field]))
    result = []
    for m in sorted(buckets):
        vals = buckets[m]
        result.append((m, sum(vals) if agg == "sum" else mean(vals)))
    return result


def try_font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_panel(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    *,
    title: str,
    unit: str,
    summary: str,
    series: list[tuple[str, list[tuple[datetime, float]], tuple]],
    threshold: float,
    threshold_label: str,
    y_max: float | None = None,
    f_title, f_sub, f_small, f_label,
    t_start: datetime,
    t_end: datetime,
):
    # card bg
    draw.rounded_rectangle([x, y, x+w, y+h], radius=14, fill=CARD_BG, outline=CARD_BR, width=1)

    # title + unit
    draw.text((x+20, y+14), title, font=f_title, fill=WHITE)
    draw.text((x+w-20, y+18), unit, font=f_small, fill=MUTED, anchor="ra")
    draw.text((x+20, y+44), summary, font=f_sub, fill=MUTED)

    # chart area
    cx = x + 72
    cy = y + 78
    cw = w - 96
    ch = h - 118

    all_vals = [v for _label, pts, _color in series for _, v in pts]
    y_top = y_max or max(threshold * 1.2, max(all_vals) * 1.1 if all_vals else threshold * 1.2, 1e-9)

    # grid
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = cy + ch - int(frac * ch)
        draw.line([(cx, gy), (cx + cw, gy)], fill=GRID, width=1)
        draw.text((cx - 6, gy - 8), f"{frac * y_top:.4g}", font=f_small, fill=MUTED, anchor="ra")

    # threshold line (dashed)
    t_frac = min(threshold / y_top, 1.0)
    ty = cy + ch - int(t_frac * ch)
    for dx in range(0, cw, 16):
        draw.line([(cx + dx, ty), (cx + min(dx + 9, cw), ty)], fill=ORANGE, width=2)
    draw.text((cx + cw - 4, ty - 14), threshold_label, font=f_small, fill=ORANGE, anchor="ra")

    # axes
    draw.line([(cx, cy), (cx, cy + ch)], fill=WHITE, width=2)
    draw.line([(cx, cy + ch), (cx + cw, cy + ch)], fill=WHITE, width=2)

    # time span
    span = (t_end - t_start).total_seconds() or 1

    # series lines
    for label, pts, color in series:
        if len(pts) < 1:
            continue
        pixel_pts = []
        for ts, val in pts:
            fx = (ts - t_start).total_seconds() / span
            fy = val / y_top
            px2 = cx + int(fx * cw)
            py2 = cy + ch - int(min(fy, 1.0) * ch)
            pixel_pts.append((px2, py2))
        if len(pixel_pts) == 1:
            px2, py2 = pixel_pts[0]
            draw.ellipse([px2-5, py2-5, px2+5, py2+5], fill=color)
        elif len(pixel_pts) >= 2:
            draw.line(pixel_pts, fill=color, width=3, joint="curve")
            for px2, py2 in pixel_pts:
                draw.ellipse([px2-4, py2-4, px2+4, py2+4], fill=color)

    # x-axis time ticks
    for frac in [0, 0.33, 0.66, 1.0]:
        tx = cx + int(frac * cw)
        ts_lbl = t_start + timedelta(seconds=frac * span)
        draw.line([(tx, cy + ch), (tx, cy + ch + 5)], fill=MUTED, width=1)
        draw.text((tx, cy + ch + 8), ts_lbl.strftime("%H:%M"), font=f_small, fill=MUTED, anchor="ma")

    # legend
    lx = cx
    for label, pts, color in series:
        draw.ellipse([lx, y + h - 22, lx + 10, y + h - 12], fill=color)
        draw.text((lx + 14, y + h - 23), label, font=f_small, fill=MUTED)
        lx += max(140, len(label) * 8 + 20)


def main():
    records, t_start, t_end = load_records()

    responses = [r for r in records if r.get("event") == "response_sent"]
    requests  = [r for r in records if r.get("event") == "request_received"]
    failures  = [r for r in records if r.get("event") == "request_failed"]
    tool_evts = [r for r in records if r.get("tool_success") is not None]

    latencies = [float(r["latency_ms"]) for r in responses]
    ttfts     = [float(r["ttft_ms"])    for r in responses]
    error_rate = 100 * len(failures) / len(requests) if requests else 0
    ret_succ   = 100 * sum(r["tool_success"] is True for r in tool_evts) / len(tool_evts) if tool_evts else 0

    lat_min  = by_minute(records, "response_sent", "latency_ms")
    ttft_min = by_minute(records, "response_sent", "ttft_ms")
    cost_min = by_minute(records, "response_sent", "cost_usd", "sum")
    tin_min  = by_minute(records, "response_sent", "tokens_in",  "sum")
    tout_min = by_minute(records, "response_sent", "tokens_out", "sum")
    qual_min = by_minute(records, "response_sent", "quality_score")

    # traffic per minute
    traf_bkt: dict[datetime, int] = defaultdict(int)
    for r in requests:
        traf_bkt[r["_ts"].replace(second=0, microsecond=0)] += 1
    traf_min = [(m, float(c)) for m, c in sorted(traf_bkt.items())]

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f28 = try_font(28)
    f20 = try_font(20)
    f15 = try_font(15)
    f13 = try_font(13)
    f11 = try_font(11)

    # ── header ────────────────────────────────────────────────────────────────
    draw.text((40, 24), "K4-L3B · LLMOps Dashboard", font=f28, fill=WHITE)
    time_lbl = (
        f"Last 60 min  ·  {t_start:%Y-%m-%d %H:%M}–{t_end:%H:%M} UTC  "
        f"·  refresh 30s  ·  source: data/logs.jsonl"
    )
    draw.text((40, 62), time_lbl, font=f15, fill=MUTED)

    # panel layout: 2 columns × 3 rows
    pad = 30
    pw  = (W - 3 * pad) // 2
    ph  = (H - 130 - 3 * pad) // 3
    cols = [pad, pad * 2 + pw]
    rows = [110, 110 + ph + pad, 110 + 2 * (ph + pad)]

    common = dict(f_title=f20, f_sub=f13, f_small=f11, f_label=f13,
                  t_start=t_start, t_end=t_end)

    # 1 — Latency
    draw_panel(draw, cols[0], rows[0], pw, ph,
        title="Latency percentiles and TTFT",
        unit="ms",
        summary=(f"P50 {pct(latencies,50):.0f} ms  ·  P95 {pct(latencies,95):.0f} ms  ·  "
                 f"P99 {pct(latencies,99):.0f} ms  ·  TTFT P95 {pct(ttfts,95):.0f} ms"),
        series=[("Latency", lat_min, BLUE), ("TTFT", ttft_min, PURPLE)],
        threshold=3000, threshold_label="SLO ≤ 3000 ms",
        **common)

    # 2 — Traffic
    draw_panel(draw, cols[1], rows[0], pw, ph,
        title="Request traffic",
        unit="requests/min",
        summary=f"{len(requests)} requests in window",
        series=[("Requests/min", traf_min, GREEN)],
        threshold=1, threshold_label="baseline ≥ 1 req/min",
        **common)

    # 3 — Errors & retrieval
    draw_panel(draw, cols[0], rows[1], pw, ph,
        title="Error rate and retrieval success",
        unit="percent",
        summary=f"Error rate {error_rate:.1f}%  ·  Retrieval success {ret_succ:.1f}%",
        series=[
            ("Error rate", [(t_start, error_rate), (t_end, error_rate)], RED),
            ("Retrieval success", [(t_start, ret_succ), (t_end, ret_succ)], GREEN),
        ],
        threshold=90, threshold_label="retrieval ≥ 90%",
        y_max=100,
        **common)

    # 4 — Cost
    total_cost = sum(float(r["cost_usd"]) for r in responses)
    draw_panel(draw, cols[1], rows[1], pw, ph,
        title="Cost over time",
        unit="USD",
        summary=f"Total ${total_cost:.4f}  ·  SLO budget ≤ $2.50",
        series=[("Cost/min (USD)", cost_min, YELLOW)],
        threshold=2.5, threshold_label="budget ≤ $2.50",
        **common)

    # 5 — Tokens
    total_in  = sum(float(r["tokens_in"])  for r in responses)
    total_out = sum(float(r["tokens_out"]) for r in responses)
    draw_panel(draw, cols[0], rows[2], pw, ph,
        title="Input and output tokens",
        unit="tokens",
        summary=f"Input total {total_in:.0f}  ·  Output total {total_out:.0f}",
        series=[("Input/min", tin_min, BLUE), ("Output/min", tout_min, PINK)],
        threshold=50000, threshold_label="≤ 50,000 tokens",
        **common)

    # 6 — Quality
    avg_quality = mean([float(r["quality_score"]) for r in responses]) if responses else 0
    draw_panel(draw, cols[1], rows[2], pw, ph,
        title="Quality proxy score",
        unit="score 0–1",
        summary=f"Average {avg_quality:.2f}  ·  SLO ≥ 0.75",
        series=[("Quality/min", qual_min, LIME)],
        threshold=0.75, threshold_label="SLO ≥ 0.75",
        y_max=1.0,
        **common)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", dpi=(144, 144))
    print(f"Saved: {OUT}  ({W}×{H}px)")
    print(f"  Records in window : {len(records)}")
    print(f"  Responses         : {len(responses)}")
    print(f"  Latency P95       : {pct(latencies,95):.0f} ms")
    print(f"  Error rate        : {error_rate:.1f}%")
    print(f"  Retrieval success : {ret_succ:.1f}%")
    print(f"  Total cost        : ${total_cost:.4f}")
    print(f"  Avg quality       : {avg_quality:.2f}")


if __name__ == "__main__":
    main()
