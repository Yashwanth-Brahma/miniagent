# Day 10 — The Codebase Q&A Agent

**Goal:** Turn the Day 8-9 retrieval research into a real product — a `search_code` tool
the Day 4 agent loop drives, answering codebase questions with verifiable file:line
citations.

**Status:** Done. Agent indexes a real 473-chunk codebase (Flask), retrieves with hybrid
search, answers with citations verified correct against source. Flushed out three latent
OpenAI-adapter bugs and measured a real model-behavior difference.

---

## What I built

```
src/miniagent/retrieval/index.py     # CodeIndex: build once, hold chunks+vectors+bm25
src/miniagent/tools/code_search.py   # @tool search_code — hybrid retrieval + citations
```

**The assembly (barely anything new):**
```
INDEX ONCE:  repo → AST chunk (Day 9) → embed + BM25 (Day 9) → held in memory
PER QUERY:   question → agent loop (Day 4, UNCHANGED) → search_code tool → cited answer
```

> The reward for clean layers: the agent loop needed ZERO changes. search_code is just
> another tool in the registry — the loop doesn't know or care it does retrieval.

---

## The one genuinely new thing: citations

The chunker tracked `source`/`start_line`/`end_line` since Day 8 — exactly for this. The
tool formats each result with its location:
```python
citation = f"{c.source}:{c.start_line}-{c.end_line}"   # e.g. flask/ctx.py:405-414
```
And the docstring instructs the agent to cite ("returns snippets WITH file:line, which you
MUST cite"). The description IS the interface (Day 3) — it makes citations appear in the
final answer.

**Verified against source (the eval instinct):** opened ctx.py:405 and app.py — the cited
lines actually contain `match_request()` / `dispatch_request()`. Citations are ACCURATE, not
hallucinated. That's the whole value proposition, confirmed.

---

## Three OpenAI-adapter bugs (all one root cause)

Today was the first time a multi-step TOOL conversation ran through the OpenAI path. Three
latent bugs surfaced at once:

1. **Tool schema shape.** `Missing required parameter: 'tools[0].type'`. My tools are
   Anthropic-shaped (`{name, description, input_schema}`); OpenAI wants
   `{type:"function", function:{name, description, parameters}}`. Added `_tools_to_openai`.
2. **`json` import.** `pydantic.json has no attribute loads` — a bad import shadowing the
   stdlib `json`. Fixed to `import json`.
3. **Tool-message serialization.** `Invalid value: 'tool_use'`. Anthropic puts tool_use as
   a content BLOCK; OpenAI wants a separate `tool_calls` field with args as a JSON STRING,
   and tool_results as separate `role:"tool"` messages (1 message → N). Rewrote
   `_to_openai_messages` to transform, not pass through.

> **The finding (extends Day 1):** "provider-agnostic" was lossier than my tests caught. I
> normalized simple MESSAGES both ways on Day 1, but tool DEFINITIONS and tool
> call/result messages only ever ran through Anthropic. The first real OpenAI tool loop
> surfaced three separate shape mismatches — schema envelope, dict-vs-JSON-string args, and
> content-blocks-vs-separate-fields. Adapters need testing on every path, not just the
> default one.

---

## The model-behavior finding (interview-gold)

Same loop, same tools, same prompt, same question ("how does Flask match a URL to a view?")
— two models, very different behavior:

| | steps | citations | quality |
|---|---|---|---|
| **Claude Haiku** | 4-10 (varied) | ctx.py:405, app.py, scaffold.py — VERIFIED correct | found the actual matching mechanism (url_adapter.match) |
| **gpt-4o-mini** | 1-2 | none, OR wrong part (cited Request class = where result is STORED, not where matching HAPPENS) | confidently incomplete — answered from prior knowledge |

**"Fewer steps" is NOT "better."** gpt-4o-mini's 1-2 step answers looked efficient but were
ungrounded or subtly wrong — it satisficed (grabbed a plausible chunk / answered from
memory). Claude persisted, dug through the code, got the mechanism right — but sometimes
WANDERED (10-15 steps, once failed to converge). Neither is ideal alone.

**Run-to-run variance is real:** Claude took 4 steps one run, 10 another, 15 (fail) another
— same question. Agent trajectories are non-deterministic; design around it, don't assume
it away.

> **The lesson:** model choice dramatically changes agent behavior for the SAME system. The
> fix is at the SYSTEM level, not "pick the good model": a stricter system prompt forces
> grounding regardless of model ("answer ONLY from search_code results; every claim cites
> file:line; if results seem tangential, search again for the mechanism, not just where
> results are stored") + a search budget to stop wandering. Measurable with a golden set
> scoring citation-accuracy AND step-count.

---

## Known limitations / deferred
- **Index is hardcoded to Python/AST chunking.** A real code-QA agent needs mixed corpora
  (code + README + docs); prose files need chunk_text, not chunk_python. Design gap noted.
- Index held in memory, rebuilt per process — a real system persists it (vector DB).
- ast.walk double-counts nested defs (method chunk + class chunk) — some duplication.
- No system-prompt hardening yet for grounding — the gpt-4o-mini fix is designed, not
  applied/measured.

---

## Interview-ready answers

> **Q: How does your codebase Q&A agent work?**
> Index a repo once — AST-chunk each file into coherent function/class units, embed them,
> build a BM25 index. A search_code tool does hybrid retrieval (the config I measured
> winning on code) and returns snippets tagged with file:line. My existing agent loop calls
> it like any tool; the tool's description instructs the model to cite. I verified the
> citations point at the real code.

> **Q: You tested two models — what did you find?**
> Same agent, Haiku vs gpt-4o-mini. gpt-4o-mini answered in 1-2 steps but ungrounded — once
> it cited the class that STORES the routing result instead of the code that DOES the
> matching. Haiku took more steps, dug through the code, and cited correctly, though it
> sometimes wandered. Fewer steps wasn't better — the fast answer was confidently
> incomplete. The fix is a stricter system prompt forcing citation-only answers plus a
> search budget, measured with a golden set.

> **Q: A bug you found integrating a second provider?**
> Three at once, all from the OpenAI tool path never being exercised before: tool schema
> envelope, a shadowed json import, and tool-call/result message serialization (Anthropic
> content-blocks vs OpenAI separate tool_calls field + role:tool messages). Taught me
> "provider-agnostic" needs testing on every code path, not just the default.

---

## Gut check — can I answer cold?
- [ ] Why did the agent loop need zero changes to become a code-QA agent?
- [ ] How do citations work end-to-end (chunker metadata → tool → answer)?
- [ ] Why did three OpenAI bugs surface today and not earlier?
- [ ] Why is gpt-4o-mini's 2-step answer NOT better than Haiku's 10-step answer?
- [ ] What's the system-level fix for the model-behavior gap?