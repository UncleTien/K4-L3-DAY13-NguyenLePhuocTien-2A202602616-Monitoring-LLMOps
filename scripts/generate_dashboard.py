from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from statistics import mean


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.svg"
WIDTH, HEIGHT = 1440, 1440
CARD_W, CARD_H = 660, 370


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_records(path: Path) -> tuple[list[dict], datetime, datetime]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        record["_ts"] = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
    latest = max((record["_ts"] for record in records), default=datetime.now(timezone.utc))
    start = latest - timedelta(minutes=60)
    return [record for record in records if record["_ts"] >= start], start, latest


def by_minute(records: list[dict], event: str, field: str, aggregation: str = "mean") -> list[float]:
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for record in records:
        if record.get("event") == event and isinstance(record.get(field), (int, float)):
            minute = record["_ts"].replace(second=0, microsecond=0)
            buckets[minute].append(float(record[field]))
    values = []
    for minute in sorted(buckets):
        items = buckets[minute]
        values.append(sum(items) if aggregation == "sum" else mean(items))
    return values


def points(values: list[float], x: int, y: int, width: int, height: int, maximum: float) -> str:
    if not values:
        return ""
    maximum = max(maximum, 1e-9)
    if len(values) == 1:
        values = [values[0], values[0]]
    return " ".join(
        f"{x + index * width / (len(values) - 1):.1f},{y + height - value / maximum * height:.1f}"
        for index, value in enumerate(values)
    )


def card(
    *, x: int, y: int, title: str, unit: str, summary: str,
    series: list[tuple[str, list[float], str]], threshold: float,
    threshold_label: str, fixed_max: float | None = None,
) -> str:
    chart_x, chart_y, chart_w, chart_h = x + 54, y + 105, CARD_W - 84, 205
    all_values = [value for _, values, _ in series for value in values]
    maximum = fixed_max or max([threshold * 1.15, *all_values, 1])
    threshold_y = chart_y + chart_h - min(threshold / maximum, 1) * chart_h
    parts = [
        f'<g><rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="18" fill="#111827" stroke="#293548"/>',
        f'<text x="{x+28}" y="{y+40}" class="title">{escape(title)}</text>',
        f'<text x="{x+28}" y="{y+69}" class="summary">{escape(summary)}</text>',
        f'<text x="{x+CARD_W-28}" y="{y+40}" text-anchor="end" class="unit">{escape(unit)}</text>',
        f'<line x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y+chart_h}" class="axis"/>',
        f'<line x1="{chart_x}" y1="{chart_y+chart_h}" x2="{chart_x+chart_w}" y2="{chart_y+chart_h}" class="axis"/>',
        f'<line x1="{chart_x}" y1="{threshold_y:.1f}" x2="{chart_x+chart_w}" y2="{threshold_y:.1f}" class="threshold"/>',
        f'<text x="{chart_x+chart_w}" y="{threshold_y-6:.1f}" text-anchor="end" class="threshold-label">{escape(threshold_label)}</text>',
        f'<text x="{chart_x-8}" y="{chart_y+5}" text-anchor="end" class="tick">{maximum:.2f}</text>',
        f'<text x="{chart_x-8}" y="{chart_y+chart_h+4}" text-anchor="end" class="tick">0</text>',
    ]
    legend_x = chart_x
    for name, values, color in series:
        polyline = points(values, chart_x, chart_y, chart_w, chart_h, maximum)
        if polyline:
            parts.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="3"/>')
        parts.extend([
            f'<circle cx="{legend_x}" cy="{y+342}" r="5" fill="{color}"/>',
            f'<text x="{legend_x+11}" y="{y+347}" class="legend">{escape(name)}</text>',
        ])
        legend_x += 170
    parts.append("</g>")
    return "".join(parts)


def render(records: list[dict], start: datetime, end: datetime) -> str:
    responses = [r for r in records if r.get("event") == "response_sent"]
    requests = [r for r in records if r.get("event") == "request_received"]
    failures = [r for r in records if r.get("event") == "request_failed"]
    tool_events = [r for r in records if "tool_success" in r and r.get("tool_success") is not None]
    latencies = [float(r["latency_ms"]) for r in responses]
    ttfts = [float(r["ttft_ms"]) for r in responses]
    traffic = by_minute(records, "request_received", "_count")
    minute_counts: dict[datetime, int] = defaultdict(int)
    for record in requests:
        minute_counts[record["_ts"].replace(second=0, microsecond=0)] += 1
    traffic = [minute_counts[key] for key in sorted(minute_counts)]
    error_rate = 100 * len(failures) / len(requests) if requests else 0
    retrieval_success = 100 * sum(r.get("tool_success") is True for r in tool_events) / len(tool_events) if tool_events else 0
    costs = by_minute(records, "response_sent", "cost_usd", "sum")
    tokens_in = by_minute(records, "response_sent", "tokens_in", "sum")
    tokens_out = by_minute(records, "response_sent", "tokens_out", "sum")
    quality = by_minute(records, "response_sent", "quality_score")
    panels = [
        card(x=40, y=135, title="Latency", unit="ms", summary=f"P50 {percentile(latencies, 50):.0f} · P95 {percentile(latencies, 95):.0f} · P99 {percentile(latencies, 99):.0f} · TTFT P95 {percentile(ttfts, 95):.0f}", series=[("Latency", latencies, "#38bdf8"), ("TTFT", ttfts, "#a78bfa")], threshold=3000, threshold_label="SLO ≤ 3000 ms"),
        card(x=740, y=135, title="Traffic", unit="requests/min", summary=f"{len(requests)} requests in selected range", series=[("Requests", traffic, "#34d399")], threshold=1, threshold_label="baseline ≥ 1 req/min"),
        card(x=40, y=535, title="Errors & retrieval", unit="percent", summary=f"Error {error_rate:.1f}% · Retrieval success {retrieval_success:.1f}%", series=[("Error rate", [error_rate], "#fb7185"), ("Retrieval success", [retrieval_success], "#34d399")], threshold=90, threshold_label="retrieval ≥ 90%", fixed_max=100),
        card(x=740, y=535, title="Cost", unit="USD", summary=f"Total ${sum(float(r['cost_usd']) for r in responses):.4f}", series=[("Cost/min", costs, "#fbbf24")], threshold=2.5, threshold_label="budget ≤ $2.50"),
        card(x=40, y=935, title="Tokens", unit="tokens", summary=f"Input {sum(float(r['tokens_in']) for r in responses):.0f} · Output {sum(float(r['tokens_out']) for r in responses):.0f}", series=[("Input/min", tokens_in, "#38bdf8"), ("Output/min", tokens_out, "#f472b6")], threshold=50000, threshold_label="≤ 50,000 tokens"),
        card(x=740, y=935, title="Quality", unit="score 0–1", summary=f"Average {mean([float(r['quality_score']) for r in responses]):.2f}" if responses else "No response data", series=[("Quality/min", quality, "#a3e635")], threshold=.75, threshold_label="quality ≥ 0.75", fixed_max=1),
    ]
    time_label = f"Last 60 minutes · {start:%Y-%m-%d %H:%M}–{end:%H:%M} UTC · refresh 30s"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<style>
text {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif; fill: #e5e7eb }}
.heading {{ font-size: 30px; font-weight: 700 }} .subtitle {{ font-size: 15px; fill: #94a3b8 }}
.title {{ font-size: 20px; font-weight: 650 }} .summary {{ font-size: 15px; fill: #cbd5e1 }}
.unit {{ font-size: 13px; fill: #94a3b8 }} .axis {{ stroke: #475569; stroke-width: 1 }}
.threshold {{ stroke: #fb923c; stroke-width: 2; stroke-dasharray: 7 5 }}
.threshold-label {{ font-size: 11px; fill: #fdba74 }} .tick {{ font-size: 10px; fill: #64748b }}
.legend {{ font-size: 12px; fill: #94a3b8 }}
</style>
<rect width="100%" height="100%" fill="#080d18"/>
<text x="40" y="60" class="heading">K4-L3B · LLMOps Dashboard</text>
<text x="40" y="91" class="subtitle">{escape(time_label)}</text>
<text x="1400" y="60" text-anchor="end" class="subtitle">source: data/logs.jsonl</text>
{''.join(panels)}
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the six-panel CP2 dashboard as SVG")
    parser.add_argument("--log", type=Path, default=LOG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records, start, end = load_records(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(records, start, end), encoding="utf-8")
    print(f"Generated {args.output} from {len(records)} records")


if __name__ == "__main__":
    main()
