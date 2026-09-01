# Week 1 — Agent Mechanics from Scratch

**Deliverable:** `miniagent` — a CLI coding/research agent with a tool registry, a real
agent loop, streaming, retries, cost accounting, and a FastAPI wrapper. Public repo,
committed daily.

**Daily shape (8h):** 2h learn → 5h build → 1h write-up (`notes/dayN.md`).
The write-up is non-negotiable — it's your interview script later.

**Guardrails for the whole week:**
- No LangChain. Not once. That's Week 2.
- Haiku-class model as default; Sonnet only to test reasoning. Hard spend cap.
- Commit daily with real messages.
- If behind: cut Day 6's HTML viewer and Day 3's schema experiment first. Everything
  else is load-bearing.

---

## Day 1 — Python for AI + provider-agnostic client  ✅ DONE

**Learn:** `uv`, Pydantic v2 (discriminated unions, `model_json_schema`), asyncio,
Anthropic Messages API + OpenAI Chat Completions (the diff).

**Build:**
- [x] Repo scaffold: `uv`, ruff, mypy (strict), pytest
- [x] `types.py` — content blocks, Message, Response, Usage
- [x] `errors.py` — LLMError with retryable flag
- [x] `llm.py` — `complete()` behind one signature, Anthropic + OpenAI adapters
- [x] `trace.py` — JSONL logging of every call, success and failure
- [x] 20+ real calls logged

**Checkpoint:** explain the request→response lifecycle; name every `stop_reason`;
explain why `content` is a list; explain why async matters; explain the provider
mapping losses both directions.

---

## Day 2 — Tokens, cost, context, embeddings  ⬅ IN PROGRESS

**Learn:**
- Karpathy, "Let's build the GPT Tokenizer" — https://www.youtube.com/watch?v=zduSFxRajkE
- tiktoken — https://github.com/openai/tiktoken
- Cosine similarity intuition + what embeddings *can't* do
- Sampling: temperature, top-p, why temp=0 isn't fully deterministic

**Build:**
- [ ] `tokens.py` — `count_tokens_openai` (local, tiktoken) + `count_tokens_anthropic`
  (async, count_tokens endpoint). Land within ~5% of a real trace's reported usage.
- [ ] `cost.py` — pricing table (per Mtok, VERIFY current prices), `estimate_cost()`,
  running session total printed after every call; add `cost` to trace records
- [ ] Context budget manager — 3 strategies: truncate-oldest, sliding window w/ pinned
  system prompt, summarize-middle (stub the summary today)
- [ ] Embedding experiment: ~200 crude chunks, brute-force cosine search with numpy,
  find 3+ queries where retrieval returns garbage — save query + result + *why*

**Write-up:** why non-English costs more tokens (+ your measured ratio); the 3 context
strategies and why truncate-oldest is a *correctness* bug; 3 documented retrieval
failures with causes; input vs output token pricing.

---

## Day 3 — Tool calling & schema design

**Learn:** Anthropic tool use (incl. parallel + tool_result block format), OpenAI
function calling (the diff), structured outputs / forced JSON.

**Build:**
- [ ] `tools/registry.py` — decorator-based `@tool`, JSON schema derived from type hints
  via Pydantic (no hand-written schemas)
- [ ] Dispatcher — name→callable, validate args *before* calling, return errors as
  `tool_result` (is_error) rather than raising
- [ ] 3 tools: `read_file`, `list_dir`, `http_get`
- [ ] Schema-quality experiment: 3 versions of one tool's description
  (terse/verbose/with examples), 10 prompts each, tabulate call-correctness

**Write-up:** what makes a tool description good — with your data, not opinions.

---

## Day 4 — The agent loop  (THE day that matters)

**Learn:**
- Anthropic, "Building Effective Agents" (read twice) —
  https://www.anthropic.com/research/building-effective-agents
- ReAct paper (skim method) — https://arxiv.org/abs/2210.03629
- Read ~300 lines of a real small agent loop (smolagents or swarm)

**Build:**
- [ ] `run(task, max_steps)` loop: call model → check stop_reason → dispatch tools
  (parallel if multiple) → append tool_results → check stop conditions
- [ ] Handle explicitly: max steps, max cost, max wall-clock, repeated-identical-call
  loop detection, tool raises, malformed args, empty response
- [ ] Give it a real task against a repo you know; watch it work and fail

**Write-up:** trace one full run step by step in prose — your "walk me through your
agent" answer.

---

## Day 5 — Real tools + not getting owned

**Learn:**
- Sandboxing: subprocess isolation, `--network=none`, why `shell=True` is a loaded gun
- Prompt injection — Simon Willison, the "lethal trifecta" post —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Permission models: allowlists, dry-run, approval gates

**Build:**
- [ ] `shell` tool — command allowlist, timeout, output truncation, working-dir jail
- [ ] `write_file` — path-traversal protection (resolve, confirm under workspace root)
- [ ] `sql_query` — read-only SQLite, enforced LIMIT
- [ ] Approval gate — `requires_approval` flag; loop pauses and prompts
- [ ] ATTACK IT — plant injection instructions in a test file; see if it obeys; fix

**Write-up:** your injection attempts, which worked, what you changed. (Differentiator —
this is your existing adversarial methodology applied to your own system.)

---

## Day 6 — Streaming, resilience, observability

**Learn:** SSE + Anthropic streaming event types; retry (exponential backoff + jitter,
which errors are retryable); tracing concepts (spans, parent/child).

**Build:**
- [ ] Streaming output, incl. streaming tool-call argument deltas
- [ ] `tenacity`-based retry wrapper with jittered backoff + budget
- [ ] Structured tracing — each step emits a span (tokens, cost, latency, tool, error)
  to JSONL
- [ ] 60-line HTML trace viewer (your React skills — 30 min) *(cut first if behind)*
- [ ] Run 10 varied tasks; collect p50/p95 latency + cost per task

**Write-up:** the latency/cost table + where the time actually goes. (Almost nobody can
answer "what's your p95?" in an interview.)

---

## Day 7 — Ship it

**Build:**
- [ ] FastAPI wrapper: `POST /run` (SSE streaming), `GET /traces/{id}`
- [ ] Dockerfile + `docker compose up`
- [ ] README: what it does, architecture diagram, real trace example, cost/latency
  numbers, and an honest "Limitations & known failure modes" section
- [ ] Deploy to Railway or Fly.io — must have a URL
- [ ] 8–10 pytest tests incl. a fake-LLM harness (loop testable without API calls)

**Write (2h):** blog post — "I wrote an agent loop from scratch instead of using
LangChain, and here's what the frameworks are actually hiding." Pull from your 7
`notes/` files. Post it (LinkedIn + GitHub profile README).

---

## End-of-week checkpoint — can I do these cold?

- [ ] Draw the agent loop on a whiteboard and name every failure mode I handled.
- [ ] Explain why an agent looped forever and 4 mechanisms that stop it.
- [ ] Quote my own p95 latency and cost per task.
- [ ] Describe a prompt injection I executed against my own system.

Hit those four and you're ahead of most people applying for these roles.

---

*Note: resource links may have moved — if one 404s, search the title. I don't have
live access to verify them.* 