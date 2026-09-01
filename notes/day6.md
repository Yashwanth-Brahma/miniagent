# Day 6 — Resilience & Observability

**Goal:** Make the agent survive flaky networks (retries), record every step (spans),
and be measurable (p50/p95, cost/task) — plus a visual trace viewer.

**Status:** Done. Retry wrapper, structured span logging, a metrics report, and a
standalone HTML waterfall viewer. Real numbers measured over 15 steps / 7 runs.

---

## What I built

```
src/miniagent/
  retry.py     # tenacity retry wrapper (backoff + jitter, retry only retryable errors)
  spans.py     # Span model + write_span() — one record per agent step
  metrics.py   # load spans, compute p50/p95 latency, cost/task, steps/task
trace_viewer.html  # standalone APM-style waterfall — bar width = latency
```

Three pieces, all wrapping each model call: streaming (feel), retries (survive),
tracing (measure). Retries + tracing built; streaming deferred to when it's needed.

---

## Part 1 — Retries with exponential backoff + jitter

**Problem:** transient failures (429 rate-limit, 529 overloaded, timeout, connection
blip) aren't real errors — they mean "try again in a moment." Without retries, one blip
kills a whole agent run.

Built on Day 1's `LLMError.retryable` flag.

```python
llm_retry = retry(
    retry=retry_if_exception(_is_retryable),          # only retryable errors
    stop=stop_after_attempt(4),                        # ceiling
    wait=wait_exponential_jitter(initial=1, max=20),   # 1s,2s,4s... + jitter, capped
    reraise=True,                                       # raise the REAL error at the end
)
# @llm_retry on complete()
```

Four decisions, each defensible:
- **retry_if_exception(_is_retryable)** — ONLY retry what's safe. 400/401 will NEVER
  succeed on retry — retrying them wastes time + money. This is why Day 1's retryable
  flag mattered.
- **exponential backoff (doubling wait)** — if the API is overloaded, retrying instantly
  adds to the pileup. Backing off gives it room to recover.
- **jitter** — if 1000 agents all hit a 429 and all wait exactly 1s, they retry in
  unison and stampede again ("thundering herd"). Random jitter spreads them out.
- **stop_after_attempt(4)** — don't retry forever (same philosophy as loop guards).
- **reraise=True** — surface the original LLMError, not tenacity's wrapper.

### Tested two ways
- Simulated: fake that fails 2x then succeeds → saw 3 attempts with lengthening pauses.
- Real: turned off wifi → retried 4x with growing backoff, then surfaced the real
  connection error on the final attempt. Also confirmed a non-retryable error fails
  immediately (1 attempt, no retries).

> **Tradeoff to name:** retries add LATENCY to genuine failures. A call that would fail
> instantly now takes ~1+2+4s of waiting before giving up. Right trade (most retryable
> errors DO succeed), but retries interact with max_wall_clock — a burst can eat a time
> budget.

---

## Part 2 — Structured tracing (spans)

Day 1 logged each API CALL. An agent RUN is many calls. To answer "where did the time
go?" I need the run as a sequence of STEPS, each with timing + metadata = a **span**.

```python
class Span(BaseModel):
    run_id: str            # one id shared by all steps in a run
    step: int
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    tool_calls: list[str] = []
    stop_reason: str = ""
    error: str | None = None
```

Instrumented the loop: `run_id = uuid[:8]` once per run; `time.perf_counter()` around
the `complete()` call (monotonic stopwatch, from Day 1); write one span per step with
tokens/cost/latency/tools/stop_reason.

Why a Pydantic model (not Day 1's plain dict): I read these back to compute stats, so a
typed model means real fields on the read side, not dict-key guessing. Write and read
agree on the shape.

> **Nuance to name:** step latency INCLUDES retry backoff, because the retry wrapper is
> inside complete(). Usually what you want (real wall-clock the user felt), but a slow
> step might be retries, not slow inference. Don't misread the tail.

---

## Part 3 — Metrics: p50 / p95 (the payoff)

### Why percentiles, not average (interview point)
If 9 steps take 1s and 1 takes 15s, the AVERAGE is 2.4s — describes none of them and
hides the outlier. Percentiles describe the real distribution:
- **p50 (median)** — half are faster; the typical experience.
- **p95** — 95% are faster, 5% slower; the "bad but not rare" experience that actually
  annoys users. This is the number teams care about because it captures the TAIL.

### Per-step vs per-task (a real distinction)
- Latency percentiles → computed over STEPS (each call is a latency event).
- Cost + step-count → computed PER RUN (group spans by run_id, sum). "How slow is a
  call" is a step question; "what does a task cost" is a run question. Mixing them =
  nonsense.

### My measured numbers (15 steps / 7 runs)
```
latency p50:    1432 ms
latency p95:    8376 ms
latency max:   14735 ms
cost/task avg:  $0.0079
cost/task p95:  $0.0205
steps/task avg: 2.1
```

**Reading the numbers (measuring vs understanding):**
- **p50 1.4s vs p95 8.4s = 6x gap.** Most calls are snappy; a minority are slow. An
  average would have smeared this into a meaningless ~3s.
- **The tail is OUTPUT-TOKEN-BOUND.** The 14.7s max step generated 1305 output tokens
  (a write_file payload); fast steps generated ~50-80. Latency is dominated by output
  token COUNT, not by number of steps or tool/network overhead.
- **Cost tail = same tasks, same cause.** The expensive tasks are the output-heavy ones
  (output ~4-5x input price, Day 2). Cost tail and latency tail are the SAME steps.
- **2.1 steps/task** — the loop terminates cleanly, no thrashing. Guards + system prompt
  working in aggregate.

> **Caveat (keep it):** 7 runs is a small sample; percentiles are directional, not
> statistically solid. I'd want 50+ runs for confidence. Claiming a rock-solid p95 off 7
> runs would be an overclaim.

---

## Part 4 — Trace viewer (standalone HTML)

APM-style waterfall (Jaeger/Datadog metaphor — the honest visualization for spans). Each
step is a bar; **bar width = latency on a scale shared across all runs**, so the slow
tail literally sticks out ~10x longer. Color encodes meaning: blue=tool step,
green=final answer, orange=error, purple=slow tail (≥p95). Hover → tokens in→out, cost,
stop_reason. Loads spans.jsonl via drag/drop (file://) or auto-fetch (when served).
Small-sample caveat baked into the UI so a demo can't overclaim.

---

## Interview-ready answers

> **Q: What's your agent's p95 latency?**
> p50 ~1.4s, p95 ~8.4s, max ~14.7s over my traced runs. The tail is output-token-bound —
> summary tasks generating long answers, not tool or network overhead. Same cause drives
> the cost tail. (Small sample though — directional, I'd want 50+ runs for confidence.)

> **Q: Why percentiles instead of average latency?**
> Averages hide the tail. One 15s call among nine 1s calls averages to 2.4s, which
> describes nothing and buries the outlier. p95 captures the "bad but not rare" case that
> actually hurts users. My p50/p95 gap (6x) is exactly that hidden tail made visible.

> **Q: How do you handle rate limits and transient failures?**
> A retry wrapper with exponential backoff + jitter, capped at 4 attempts, that ONLY
> retries retryable errors (429/529/timeout) and fails fast on 400/401. Backoff avoids
> piling onto an overloaded API; jitter avoids the thundering herd when many clients
> retry in unison. I tested it by killing my wifi — 4 retries with growing backoff, then
> the real error.

> **Q: How do you observe an agent run?**
> One span per step to JSONL — run_id, latency, tokens, cost, tool names, stop_reason.
> That feeds a metrics report (p50/p95, cost/task) and a waterfall viewer where bar width
> is latency, so the slow tail is visible at a glance.

---

## Known limitations / deferred
- Streaming not yet wired (deferred — not needed until the web server).
- Step latency includes retry waits — a slow step could be retries, not inference.
- Percentiles off a tiny sample — directional only.
- Metrics read the whole spans.jsonl each time — fine now, would need windowing at scale.

---

## Gut check — can I answer cold?
- [ ] Why retry 429/529 but NOT 400/401?
- [ ] What is jitter and what problem does it solve?
- [ ] Why is average latency misleading? What does p95 capture?
- [ ] Why compute latency per-step but cost per-run?
- [ ] What drives my latency AND cost tail (one answer)?
- [ ] Why does step latency sometimes include time that isn't inference?