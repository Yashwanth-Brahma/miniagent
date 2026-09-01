# Day 4 — The Agent Loop

**Goal:** Assemble the Day 1–3 pieces into an autonomous loop that chains tool calls
until a task is done — and can't run away.

**Status:** Done. Working loop with 3 guards (max_steps, max_cost, loop detection), a
structured AgentResult, and a system prompt. All three guards triggered live.

---

## The core realization

The loop invents nothing. It orchestrates pieces I already built:
`complete()` (Day 1), `dispatch()` + `all_tool_schemas()` (Day 3), cost tracking (Day 2).

```
  call the model
       │
   stop_reason?
    ├── end_turn  → DONE, return the answer
    └── tool_use  → dispatch each tool → append results → loop back to top
```

Day 3 did ONE round trip by hand. Day 4 wraps it in a loop so the model can chain many:
read a file → decide it needs another → fetch a URL → answer.

---

## The naive loop (works, but dangerous)

```python
while True:
    resp = await complete(history, model=model, tools=tools, max_tokens=max_tokens)
    history.append(resp.to_message())
    if resp.stop_reason != "tool_use":
        return "\n".join(b.text for b in resp.content if b.type == "text")
    results = [dispatch(block) for block in resp.tool_uses]
    history.append(Message(role="user", content=results))
```

Three ways this hurts you in production:
1. **Infinite loop** — model keeps asking for tools, never says end_turn → runs forever.
2. **Budget blowout** — finishes, but after 40 expensive calls, no ceiling.
3. **No visibility** — no idea how many steps it took or why it stopped.

Real agents put a circuit breaker on the loop. That's the interesting part of the day.

---

## Guard 1 — max_steps (blunt: catches behavioral runaway)

`while True` → `for step in range(max_steps)`. Hard ceiling on iterations.

```python
for step in range(max_steps):
    ...
# fell out of the loop = hit the limit without finishing
return AgentResult(output="...", stop_reason="max_steps", steps=max_steps, cost=run_spend)
```

**Triggered it live:** added a tool that always returns "retry", asked the agent to keep
trying. Naive loop looped forever (killed with Ctrl-C after ~10 calls, watching cost
climb). With max_steps=5 it stopped cleanly at step 5.

**Design decision at the limit:** what happens when you hit it? I return a "stopped"
result. Alternative: do one final call telling the model "you're out of steps, answer
now." Both valid — the point is I DECIDED, instead of letting it run wild. (Interview:
"what happens when your agent hits its step limit?")

---

## Guard 2 — max_cost (resource: catches expensive runaway)

max_steps caps HOW MANY calls, not their SIZE. 5 calls each stuffing 100K tokens into
context stays under the step limit but costs a fortune. Steps and money are different
axes → separate ceiling.

```python
start_spend = get_session_spend()          # snapshot at run start (per-run, not global)
for step in range(max_steps):
    run_spend = get_session_spend() - start_spend
    if run_spend >= max_cost:              # CHECK BEFORE the call, not after
        return AgentResult(..., stop_reason="max_cost")
    resp = await complete(...)
    ...
```

Two subtleties:
- **Check at the TOP, before complete().** Check before you spend, not after — else you
  always overshoot by one call.
- **start_spend snapshot** — get_session_spend() is a global process total. Subtracting
  the start gives THIS run's spend, so calling run() twice doesn't inherit prior spend.

**Triggered it live:** set max_cost=$0.001. Stopped at step 1 with the max_cost message
(not max_steps) — proving the brakes are independent.

### Known limitation: cost guard overshoots by one call
It stopped at $0.0013 against a $0.0010 limit. The guard checks before a call but only
sees spend from COMPLETED calls — step 1's check saw $0.00, allowed the call, which cost
$0.0013. So a post-hoc cost guard always overshoots by up to one call. A hard budget
would estimate the next call's cost and refuse pre-emptively.

---

## Guard 3 — loop detection (surgical: catches "stuck" early + diagnostically)

max_steps/max_cost are blunt safety nets — they stop a stuck agent EVENTUALLY, wasting
all 10 steps first. Loop detection is surgical: notices the model repeating itself and
stops at step 3, telling you exactly what it was stuck on.

**The insight:** a stuck model calls the IDENTICAL tool with IDENTICAL args repeatedly.
Fingerprint each call, count repeats, stop at the threshold.

```python
def _call_signature(block) -> str:
    return f"{block.name}:{json.dumps(block.input, sort_keys=True)}"
    # sort_keys=True: {"a":1,"b":2} and {"b":2,"a":1} are the SAME call

call_counts: dict[str, int] = {}
for block in resp.tool_uses:
    sig = _call_signature(block)
    call_counts[sig] = call_counts.get(sig, 0) + 1
    if call_counts[sig] >= max_repeats:
        return AgentResult(..., stop_reason="loop_detected",
                           output=f"'{block.name}' called identically {max_repeats}x")
```

**Triggered it live:** the always-"retry" task with generous step/cost limits. Stopped at
**step 3** with "check_status called with identical args 3 times — agent appears stuck"
— BEFORE exhausting the 10 steps. Caught stuck early and named the cause.

### Known limitation: only catches EXACT repetition
check_status("database") → check_status("db") → check_status("database") has different
signatures and slips through. Real systems use fuzzier detection (semantic similarity,
or "no new info gained in N steps"). Exact-match is the right 80/20; noted.

---

## Three guards, three failure modes (the interview framing)

| Guard | Type | Catches |
|---|---|---|
| max_steps | blunt | general behavioral runaway (won't stop asking) |
| max_cost | resource | expensive runaway, independent of step count |
| loop detection | surgical | the specific "stuck repeating itself" pattern, early + diagnostic |

> "Step and cost limits are safety nets — they stop a stuck agent eventually. Loop
> detection is diagnostic — it catches the most common stuck-pattern early and tells you
> what went wrong. You want both the blunt nets and the surgical one, because they fail
> independently: a model can blow the budget in 3 expensive steps or loop cheaply 50x."

---

## Finish line — structured result + system prompt

### AgentResult (operable, not just eyeball-able)
Returning a bare string means the caller can't tell "done" from "gave up" without
string-matching. A structured result fixes that:
```python
class AgentResult(BaseModel):
    output: str
    stop_reason: str    # completed | max_steps | max_cost | loop_detected
    steps: int
    cost: float
```
Every exit reports how it ended, step count, and cost. Day 6 metrics become trivial —
the data's already structured. FastAPI (Day 7) can check `result.stop_reason` and log
`result.cost` programmatically.

### System prompt (reduces how often guards fire)
```
Use tools to gather real info rather than guessing. When you have enough to answer,
respond directly without more tool calls. If a tool fails repeatedly, stop and report
instead of retrying endlessly. Be concise.
```
The "stop instead of retrying endlessly" line nudges the model to self-terminate → loop
detection fires LESS often. Defense in depth: the prompt reduces stuck-ness, the guard
catches what slips through.

---

## Bug caught by cross-checking (eval instinct on my own code)

First AgentResult reported `cost=0.0014` but the call prints summed to ~$0.0093 — it
reported roughly the FIRST call only.

**Cause:** the success path returned the `run_spend` captured at the TOP of the loop
(before the final, expensive complete() ran). Stale read.

**Fix:** recompute spend right before building the success result, not reuse the
top-of-loop value.

**Lesson:** WHERE you read a value in a loop matters. The guard CHECK belongs at the top
(check before you spend); the cost REPORT belongs at the exit (measure after you've
spent). Same variable, two correct read-points. This bug only surfaced by cross-checking
the reported number against the actual call costs — the run "succeeded", so nothing else
would have flagged it.

---

## Interview-ready answers

> **Q: Walk me through your agent loop.**
> A for-loop bounded by max_steps. Each iteration: call the model with the conversation
> and tool schemas; append its turn. If stop_reason isn't tool_use, it's done — return
> the text. Otherwise dispatch each requested tool, append the results as a user message,
> and loop. Every iteration checks guards first: a cost ceiling and loop detection. It
> returns a structured result with stop_reason, step count, and cost.

> **Q: How do you stop an agent from running forever?**
> Three independent guards. max_steps caps iterations. max_cost caps spend (different
> axis — a model can loop cheaply or spend fast in few steps). Loop detection fingerprints
> each tool call (name + sorted args) and stops when the same call repeats, which catches
> "stuck" early and tells me what it was stuck on. The system prompt also tells the model
> to self-terminate, so guards fire less.

> **Q: What happens when the agent hits a limit?**
> It returns an AgentResult with the specific stop_reason (max_steps / max_cost /
> loop_detected), so the caller can distinguish success from giving up and log why.

> **Q: What are the limitations?**
> Cost guard overshoots by up to one call (checks post-hoc). Loop detection only catches
> exact-arg repetition, not semantic loops. Both are acceptable 80/20 choices I noted
> rather than over-engineering.

---

## Gut check — can I answer cold?
- [ ] Why does the loop "invent nothing"? What pieces does it orchestrate?
- [ ] Why are max_steps and max_cost separate guards (not redundant)?
- [ ] Why is loop detection better than just a step cap? What does it catch that the cap misses?
- [ ] Why fingerprint with sort_keys=True?
- [ ] Why did the cost report come out wrong, and what's the general lesson?
- [ ] Why return an AgentResult object instead of a string?