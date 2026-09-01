# miniagent

An LLM agent built from scratch in Python — no LangChain, no orchestration framework —
to understand what those frameworks actually do under the hood.

It's a coding/research agent with a provider-agnostic model client, a tool layer built
from type hints, an autonomous loop with runaway protection, hardened tools that survive
adversarial testing, retry/resilience, and real observability (p50/p95 latency, cost per
task). It runs as a CLI or an HTTP service.

---

## Why build it from scratch

Most agent tutorials wire up a framework and call it done. This project takes the
opposite approach: implement every layer by hand — the model adapter, the tool-schema
generation, the agent loop, the guards, the security — so that every design decision is
one I can explain and defend, not one hidden behind an abstraction.

The result is small (a few hundred lines of core code) but complete, and every piece has
a written rationale in [`notes/`](./notes).

---

## Architecture

```
  user task
     │
     ▼
  agent loop  ──► calls the model ──► provider-agnostic client (Anthropic / OpenAI)
     │                                        │
     │   stop_reason == tool_use              │  retry wrapper (backoff + jitter)
     ▼                                        ▼
  dispatcher ──► runs a tool ──► result ──► back into the loop
     │
     ├─ guards: max_steps · max_cost · loop detection
     └─ every step logged as a span (tokens, cost, latency, tool, stop_reason)
```

Core modules:

| Module | Responsibility |
|---|---|
| `llm.py` | One `complete()` over both Anthropic and OpenAI; normalizes content blocks, stop reasons, usage |
| `types.py` | Pydantic models for messages, content blocks, `AgentResult` |
| `tools/registry.py` | `@tool` decorator — generates JSON schema from a function's type hints |
| `tools/dispatch.py` | Runs a requested tool; every failure becomes a message, never a crash |
| `agent.py` | The autonomous loop with three independent runaway guards |
| `retry.py` | Exponential backoff + jitter; retries only retryable errors |
| `spans.py` / `metrics.py` | Per-step tracing and p50/p95 / cost-per-task reporting |
| `server.py` | FastAPI wrapper (`/run`, `/health`, `/metrics`) |

---

## Highlights

**Provider-agnostic by design.** The whole codebase speaks one internal (Anthropic-
shaped) format; an adapter normalizes OpenAI at the edges. The mapping is lossy in both
directions (different stop reasons, OpenAI's tool args are a JSON string that can be
malformed) and the adapter absorbs that so the rest of the code never knows which
provider it's talking to.

**Tools from type hints.** You write a normal typed Python function; a decorator reads
its signature via `inspect` and generates the JSON schema via Pydantic. No hand-written
schemas.

```python
@tool
def read_file(path: Annotated[str, Field(description="Path relative to workspace")],
              max_bytes: int = 50_000) -> str:
    """Read a UTF-8 text file and return its contents."""
    ...
```

**Runaway protection, three independent guards.** `max_steps` (behavioral runaway),
`max_cost` (resource runaway — a different axis), and loop detection (fingerprints each
tool call by name + sorted args, stops when the model repeats itself). Each was verified
by triggering the failure it prevents.

**Security, tested by attacking it.** Dangerous tools are hardened with code-level
defenses that don't depend on the model's judgment: `shell` has a command allowlist and
runs with `shell=False`; `write_file` resolves paths and refuses anything outside the
workspace; `sql_query` uses a read-only connection. I forced the model to attempt each
attack — it complied fully and the code refused every time — and demonstrated a
successful injection against a deliberately-undefended canary tool to show the difference
is the code, not the model. See [`notes/day5.md`](./notes/day5.md).

**Observability.** Every step is logged as a span. A metrics report and a standalone
[trace viewer](./trace_viewer.html) (an APM-style waterfall where bar width = latency)
turn those spans into numbers and pictures.

---

## Measured performance

Over a sample of traced runs (small sample — directional, not statistically solid):

| Metric | Value |
|---|---|
| Latency p50 | ~1.4 s |
| Latency p95 | ~8.4 s |
| Latency max | ~14.7 s |
| Cost / task (avg) | ~$0.008 |
| Steps / task (avg) | ~2.1 |

The latency and cost tails are both driven by the same thing: **output token count.**
Summary tasks that generate long answers dominate; tool and network overhead are minor.

---

## Running it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Set `ANTHROPIC_API_KEY`
(and optionally `OPENAI_API_KEY`) in a `.env` file.

```bash
uv sync

# CLI
uv run python -m miniagent "Read quorra_docs.md and summarize backpressure."

# HTTP server (interactive docs at http://localhost:8000/docs)
uv run uvicorn miniagent.server:app --port 8000
```

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What files are in the workspace? Use list_dir."}'
```

### Docker

```bash
docker build -t miniagent .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" miniagent
```

---

## Security note on the deployed surface

A public endpoint is a different trust boundary than a local CLI. The server exposes
**only the read-only tools** (`read_file`, `list_dir`, `http_get`) — the dangerous tools
(`shell`, `write_file`, `sql_query`) are intentionally *not* registered on the deployed
surface. Exposing a command runner on a public URL would be handing the internet a shell,
hardened or not.

---

## Limitations & known trade-offs

Honest about what this is not:

- **Prompt injection is mitigated, not solved** — no system reliably separates
  instructions from data. The strategy is to limit blast radius (code-level tool
  defenses + human approval), not to make the model un-foolable.
- **Server responses are synchronous** — a production version would stream step updates
  over SSE. The streaming groundwork exists but isn't wired into the endpoint.
- **Loop detection catches exact repetition only** — a semantically-looping agent
  (`status("db")` vs `status("database")`) slips through. Real systems use fuzzier
  detection.
- **Cost guard can overshoot by one call** — it checks spend before each call but only
  sees completed calls, so it can exceed the budget by the final call's cost.
- **Percentiles are off a small sample** — directional, not production-grade statistics.
- **Context management strategies exist but summarize-middle is a stub** — the real LLM
  summary isn't wired in.

These are documented deliberately. Naming what a system doesn't do is part of
understanding it.

---

## Notes

The [`notes/`](./notes) directory has a per-day write-up of the design decisions,
experiments, and bugs encountered building this — including a tool-description quality
experiment, a naive-retrieval failure analysis, and the security attack report.