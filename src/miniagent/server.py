from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from miniagent.agent import run
from miniagent.metrics import load_spans, percentile
import miniagent.tools.registry   # side-effect: register the safe tools

app = FastAPI(title="miniagent", description="An agent built from scratch.")


class RunRequest(BaseModel):
    task: str
    model: str = "claude-haiku-4-5-20251001"
    max_steps: int = 10
    max_cost: float = 0.50


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
async def run_agent(req: RunRequest):
    result = await run(
        req.task,
        model=req.model,
        max_steps=req.max_steps,
        max_cost=req.max_cost,
    )
    return result          # AgentResult -> JSON automatically


@app.get("/metrics")
def metrics() -> dict[str, float | int]:
    spans = load_spans()
    if not spans:
        return {"steps": 0}
    lat = [s.latency_ms for s in spans]
    return {
        "steps": len(spans),
        "latency_p50_ms": round(percentile(lat, 50), 1),
        "latency_p95_ms": round(percentile(lat, 95), 1),
    }