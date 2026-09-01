from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

TRACE_DIR = Path("traces")


class Span(BaseModel):
    run_id: str
    step: int
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    tool_calls: list[str] = Field(default_factory=list)   # names of tools run this step
    stop_reason: str = ""
    error: str | None = None


def write_span(span: Span) -> None:
    TRACE_DIR.mkdir(exist_ok=True)
    with (TRACE_DIR / "spans.jsonl").open("a") as f:
        f.write(span.model_dump_json() + "\n")