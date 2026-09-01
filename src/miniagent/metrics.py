from __future__ import annotations

import json
from pathlib import Path

from miniagent.spans import Span

TRACE_DIR = Path("traces")


def load_spans() -> list[Span]:
    path = TRACE_DIR / "spans.jsonl"
    if not path.exists():
        return []
    return [Span.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    # index at the p-th percentile (linear, good enough)
    k = (len(s) - 1) * (p / 100)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)   # interpolate between the two nearest


def report() -> None:
    spans = load_spans()
    if not spans:
        print("no spans yet")
        return

    latencies = [s.latency_ms for s in spans]

    # group spans by run to get PER-TASK totals
    runs: dict[str, list[Span]] = {}
    for s in spans:
        runs.setdefault(s.run_id, []).append(s)
    costs_per_run = [sum(s.cost for s in run) for run in runs.values()]
    steps_per_run = [len(run) for run in runs.values()]

    print(f"steps recorded:   {len(spans)}  across {len(runs)} runs")
    print(f"latency p50:      {percentile(latencies, 50):.0f} ms")
    print(f"latency p95:      {percentile(latencies, 95):.0f} ms")
    print(f"latency max:      {max(latencies):.0f} ms")
    print(f"cost/task avg:    ${sum(costs_per_run)/len(costs_per_run):.4f}")
    print(f"cost/task p95:    ${percentile(costs_per_run, 95):.4f}")
    print(f"steps/task avg:   {sum(steps_per_run)/len(steps_per_run):.1f}")