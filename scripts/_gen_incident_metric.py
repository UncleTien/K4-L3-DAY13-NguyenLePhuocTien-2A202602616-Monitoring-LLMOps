"""Generate 12-incident-metric.png using PIL — no external SVG dependency."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
OUT = ROOT / "submission" / "evidence" / "12-incident-metric.png"

# ── palette ────────────────────────────────────────────────────────────────────
BG        = (8,  13,  24)
CARD_BG   = (17, 24,  39)
CARD_BR   = (41, 53,  72)
YELLOW    = (251, 191, 36)
ORANGE    = (251, 146, 60)
RED       = (251, 113, 133)
WHITE     = (229, 231, 235)
MUTED     = (148, 163, 184)
GRID      = (55,  65,  81)
BASELINE_C= (52, 211, 153)   # green — normal
SPIKE_C   = (251, 113, 133)  # red   — incident

W, H = 1200, 720


def load_data():
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        r["_ts"] = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        records.append(r)

    responses = [r for r in records if r.get("event") == "response_sent"]
    responses.sort(key=lambda r: r["_ts"])

    # bucket per minute
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for r in responses:
        minute = r["_ts"].replace(second=0, microsecond=0)
        buckets[minute].append(float(r["cost_usd"]))

    minutes = sorted(buckets)
    # cost per minute = sum of costs in that minute
    costs = [(m, sum(buckets[m])) for m in minutes]

    # get all individual cost_usd values with timestamp for scatter annotation
    points_raw = [(r["_ts"], float(r["cost_usd"]), r.get("correlation_id", "")) for r in responses]

    return costs, points_raw, responses


def try_font(size):
    for name in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/Library/Fonts/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def main():
    costs, points_raw, responses = load_data()

    if not costs:
        print("No data found.")
        return

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title  = try_font(28)
    f_sub    = try_font(16)
    f_label  = try_font(14)
    f_small  = try_font(12)
    f_badge  = try_font(13)

    # ── header ────────────────────────────────────────────────────────────────
    draw.text((40, 28), "K4-L3B · LLMOps Dashboard — Cost Panel (Incident Evidence)", font=f_title, fill=WHITE)

    all_ts = [r["_ts"] for r in responses]
    t_min  = min(all_ts)
    t_max  = max(all_ts)
    draw.text((40, 68), f"Time range: {t_min:%Y-%m-%d %H:%M}–{t_max:%H:%M} UTC  |  source: data/logs.jsonl", font=f_sub, fill=MUTED)

    # ── card background ───────────────────────────────────────────────────────
    cx, cy, cw, ch = 40, 108, W - 80, H - 148
    draw.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=16, fill=CARD_BG, outline=CARD_BR, width=1)

    draw.text((cx+24, cy+20), "Cost per Request (USD)", font=f_title, fill=WHITE)

    # stats
    all_costs_vals = [float(r["cost_usd"]) for r in responses]
    incident_costs = [c for _, c, cid in points_raw if c > 0.005]
    baseline_costs = [c for _, c, cid in points_raw if c <= 0.005]
    avg_b = sum(baseline_costs)/len(baseline_costs) if baseline_costs else 0
    avg_i = sum(incident_costs)/len(incident_costs) if incident_costs else 0
    ratio = avg_i / avg_b if avg_b else 0

    stats_txt = (
        f"Baseline avg: ${avg_b:.5f}  |  Incident avg: ${avg_i:.5f}  |  "
        f"Ratio: {ratio:.1f}×  |  SLO budget: $0.005/req"
    )
    draw.text((cx+24, cy+56), stats_txt, font=f_sub, fill=MUTED)

    # ── chart area ────────────────────────────────────────────────────────────
    px, py = cx+64, cy+96
    pw, ph = cw - 96, ch - 160

    max_cost = max(c for _, c, _ in points_raw) * 1.18
    slo_val  = 0.005   # SLO threshold per request

    # grid lines
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = py + ph - int(frac * ph)
        draw.line([(px, gy), (px+pw, gy)], fill=GRID, width=1)
        val = frac * max_cost
        draw.text((px - 58, gy - 8), f"${val:.5f}", font=f_small, fill=MUTED)

    # SLO threshold line
    slo_y = py + ph - int((slo_val / max_cost) * ph)
    draw.line([(px, slo_y), (px+pw, slo_y)], fill=ORANGE, width=2)
    for dash_x in range(px, px+pw, 18):
        draw.line([(dash_x, slo_y), (min(dash_x+10, px+pw), slo_y)], fill=ORANGE, width=2)
    draw.text((px+pw - 160, slo_y - 20), "SLO budget ≤ $0.005", font=f_badge, fill=ORANGE)

    # axes
    draw.line([(px, py), (px, py+ph)], fill=WHITE, width=2)
    draw.line([(px, py+ph), (px+pw, py+ph)], fill=WHITE, width=2)

    # scatter plot — individual request costs
    total_secs = (t_max - t_min).total_seconds() or 1
    INCIDENT_THRESHOLD = 0.005

    drawn_labels = []   # avoid overlap
    for ts, cost, cid in points_raw:
        frac_x = (ts - t_min).total_seconds() / total_secs
        frac_y = cost / max_cost
        dot_x = px + int(frac_x * pw)
        dot_y = py + ph - int(frac_y * ph)
        color = SPIKE_C if cost > INCIDENT_THRESHOLD else BASELINE_C
        r = 8 if cost > INCIDENT_THRESHOLD else 5
        draw.ellipse([dot_x-r, dot_y-r, dot_x+r, dot_y+r], fill=color)

    # annotate the highest-cost challenge requests
    challenge_ids = {"req-765634b5", "req-38151f2e", "req-c6d316ec", "req-7789e7f7", "req-636704cd"}
    labeled = 0
    for ts, cost, cid in sorted(points_raw, key=lambda x: -x[1]):
        if cid not in challenge_ids or labeled >= 3:
            continue
        frac_x = (ts - t_min).total_seconds() / total_secs
        frac_y = cost / max_cost
        dot_x = px + int(frac_x * pw)
        dot_y = py + ph - int(frac_y * ph)
        short = cid[-8:] if cid else ""
        lbl = f"{short}  ${cost:.5f}"
        offset_y = -28 if labeled % 2 == 0 else 12
        draw.text((dot_x - 60, dot_y + offset_y), lbl, font=f_small, fill=RED)
        draw.line([(dot_x, dot_y-10), (dot_x, dot_y-4)], fill=RED, width=1)
        labeled += 1

    # incident time band annotation
    inc_start_s = None
    inc_end_s   = None
    for ts, cost, cid in points_raw:
        if cid in challenge_ids:
            secs = (ts - t_min).total_seconds()
            if inc_start_s is None or secs < inc_start_s:
                inc_start_s = secs
            if inc_end_s is None or secs > inc_end_s:
                inc_end_s = secs

    if inc_start_s is not None:
        bx1 = px + int(inc_start_s / total_secs * pw) - 12
        bx2 = px + int(inc_end_s   / total_secs * pw) + 12
        band_color = (251, 113, 133, 40)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([bx1, py, bx2, py+ph], fill=(220, 50, 50, 45))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.line([(bx1, py), (bx1, py+ph)], fill=RED, width=2)
        draw.line([(bx2, py), (bx2, py+ph)], fill=RED, width=2)
        draw.text((bx1 + 4, py + 6), "⬅ INCIDENT WINDOW", font=f_badge, fill=RED)

    # x-axis time labels
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        tx = px + int(frac * pw)
        ts_label = t_min + timedelta(seconds=frac * total_secs)
        draw.line([(tx, py+ph), (tx, py+ph+5)], fill=MUTED, width=1)
        draw.text((tx - 30, py+ph+8), ts_label.strftime("%H:%M:%S"), font=f_small, fill=MUTED)

    # ── legend ────────────────────────────────────────────────────────────────
    lx, ly = px, py + ph + 42
    draw.ellipse([lx, ly, lx+12, ly+12], fill=BASELINE_C)
    draw.text((lx+18, ly-1), f"Normal request (baseline avg ${avg_b:.5f})", font=f_label, fill=MUTED)
    lx2 = lx + 360
    draw.ellipse([lx2, ly, lx2+12, ly+12], fill=SPIKE_C)
    draw.text((lx2+18, ly-1), f"Incident request (avg ${avg_i:.5f}, {ratio:.1f}× baseline)", font=f_label, fill=RED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", dpi=(144, 144))
    print(f"Saved: {OUT}")
    print(f"  Baseline requests : {len(baseline_costs)}  avg cost ${avg_b:.5f}")
    print(f"  Incident requests : {len(incident_costs)}  avg cost ${avg_i:.5f}  ({ratio:.1f}× baseline)")


if __name__ == "__main__":
    main()
