# src/miniagent/trace.py
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

TRACE_DIR = Path("traces")

def log_call(
    *,
    provider: str,
    model: str,
    request: dict[str, Any],
    response: dict[str, Any] | None,
    error: str | None,
    latency_ms: float,
    cost_usd: str
) -> None:
    TRACE_DIR.mkdir(exist_ok=True)
    record = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "request": request,
        "response": response,
        "error": error,
        "cost_usd": cost_usd,
    }
    with (TRACE_DIR / "calls.jsonl").open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")