# Day 1 — Provider-agnostic LLM client

**Goal:** Build the foundation of `miniagent` — typed message models, a `complete()`
function that works against both Anthropic and OpenAI behind one signature, and
trace logging of every call.

**Status:** Done. `types.py`, `llm.py`, `errors.py`, `trace.py` all working and
committed. 20+ real calls logged to `traces/calls.jsonl`.

---

## What I built

```
src/miniagent/
  types.py    # Pydantic models: content blocks, Message, Response, Usage
  errors.py   # LLMError with a retryable flag
  llm.py      # complete() + per-provider adapters + serializers
  trace.py    # log_call() — appends one JSONL line per call
```

The core idea: **one internal format, two providers.** Everything inside the agent
speaks Anthropic-shaped types. The adapters translate to/from OpenAI at the edges.
The rest of the codebase never knows which provider it's talking to.

---

## Key design decisions (and how to defend them)

### 1. Content is a list of blocks, not a string
A single model turn can contain text *and* a request to call a tool. So message
content is `list[ContentBlock]` where each block is one of `TextBlock`,
`ToolUseBlock`, `ToolResultBlock`.

- `text` — plain text (model or me)
- `tool_use` — "call this tool with these args" (model only). Its `id` must be
  echoed back **exactly**.
- `tool_result` — what the tool returned (my harness). Its `tool_use_id` must
  match a `tool_use.id` in the previous message, or the API returns a 400.

### 2. Anthropic's shape is the internal shape
Anthropic's content-block format is strictly more expressive than OpenAI's
`content + tool_calls`. Normalizing toward the richer format loses nothing;
normalizing the other way would. So the OpenAI adapter does the extra work.

### 3. Discriminated union for content blocks
```python
ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]
```
The `discriminator="type"` tells Pydantic to read the `type` field first and jump
straight to the right class — one validation attempt, one clear error. Without it,
Pydantic tries each member in order and gives a confusing wall of errors when
nothing matches.

### 4. `is_error` on tool results = robustness
When a tool throws, I don't crash the loop. I set `is_error=True`, put the error
message in `content`, and send it back to the model. The model reads the error and
usually recovers on its own. This one boolean is a surprising amount of what makes
an agent feel resilient.

### 5. Keep the raw payload
`Response.raw` holds the untouched provider response. When something behaves oddly,
I want the original, not my normalized version.

---

## The two roles: user vs assistant

- `user` = input to the model (my prompt, tool results, retrieved context)
- `assistant` = output from the model (what it said)

Things that trip people up:
- The API is **stateless**. Every call I send the whole conversation. The
  `assistant` messages aren't server memory — they're context I reconstruct.
- Anthropic requires alternation starting with `user`. Two `user` messages in a row
  is an error (OpenAI is looser — the adapter absorbs this).
- **Tool results go in a `user` message.** The "user" in that turn is my harness,
  not a human. Feels wrong the first time, then it clicks.
- `system` is a **top-level parameter** in Anthropic, not a message with a role.
- Prefill: if the last message is `assistant`, the model *continues* it instead of
  starting fresh. Ending with `assistant: "{"` makes JSON output more likely.
  (Also the mechanism behind a class of jailbreaks — forge an assistant turn.)

---

## Provider mapping losses (INTERVIEW GOLD)

> "How did you normalize across providers?"

The mapping is **lossy in both directions** — this is the honest, senior answer:

| Concern | Anthropic | OpenAI | What I did |
|---|---|---|---|
| Stop reason | `end_turn`/`tool_use`/`max_tokens`/`stop_sequence` | `stop`/`tool_calls`/`length`/`content_filter` | Explicit map each way; unknowns → `other` |
| No counterpart | `stop_sequence` | `content_filter` | Both collapse toward `other` — lossy |
| Tool args | pre-parsed `dict` | JSON **string**, can be malformed | Parse in adapter; on `JSONDecodeError` → `{}` + is_error result |
| Tool results | one `user` msg w/ N result blocks | N separate `role:"tool"` msgs | Serializer **expands** 1 message → N |
| Cache tokens | flat read/write fields | nested `prompt_tokens_details.cached_tokens`, read-only | Normalized to Anthropic shape; dropped write-cache for OpenAI |
| Usage names | `input_tokens`/`output_tokens` | `prompt_tokens`/`completion_tokens` | Renamed in adapter, not caller |

The serializer expansion (1 → N messages) is the neatest example: the agent loop
never learns that OpenAI wants separate tool messages. That's the payoff of the
adapter pattern.

---

## `try / except / finally` logging pattern

```python
start = time.perf_counter()
response, error = None, None
try:
    response = await _dispatch(...)
    return response
except Exception as e:
    error = e
    raise               # re-raise, don't swallow
finally:
    log_call(...)       # ALWAYS runs — success, failure, and return
```

- Catch only to **record** the error, then `raise` re-throws with the traceback
  intact. `finally` runs on every path, so logging happens exactly once.
- `time.perf_counter()` for **duration** (monotonic, immune to clock changes).
  `time.time()` for the wall-clock timestamp. Each for its right job.
- `repr(error)` not `str(error)` — `repr` includes the class name, and the type is
  half of debugging.

---

## Why JSONL for traces

One JSON object per line, not a wrapped array.
- **Appending is trivial** — write one line, done. A JSON array would need
  read-parse-append-rewrite every time.
- **Crash-safe** — a crash mid-write loses the last half-line; every line above it
  is still valid. A half-written array is broken entirely.
- `json.dumps(record, default=str)` — `default=str` is a seatbelt so a
  non-serializable value stringifies instead of crashing the logger. Logging must
  never be the thing that breaks the request it's recording.

---

## Why async at all (the loop is sequential!)

Common interview trap. "It's faster" is the wrong answer for a single sequential
loop. Real reasons:
1. **Parallel tool calls** within one turn (`asyncio.gather`).
2. **Streaming** — yielding tokens as they arrive.
3. **The FastAPI server** (Day 7) handles concurrent runs on one worker.
4. **Clean timeouts / cancellation** instead of duct-taped threads.
5. A **sync HTTP call blocks the entire event loop** — one sync client library
   poisons the whole design. (This is why the clients are `AsyncAnthropic`/
   `AsyncOpenAI`, not the sync versions.)

---

## Python things I learned (coming from JS/TS)

- `self` is `this`, but **explicit** — it's the first parameter of every method, and
  Python passes it automatically when you call `obj.method()`.
- `super().__init__(...)` calls the parent constructor — needed so `Exception`
  stores the message and tracebacks display properly.
- Bare `*` in a signature forces keyword-only args after it:
  `def f(self, msg, *, retryable)` → must call `f("x", retryable=True)`. Good for
  booleans, where a positional `True` tells the reader nothing.
- `Literal["user", "assistant"]` = only those exact strings are valid; caught by
  both mypy (static) and Pydantic (runtime).
- Module-level clients = created once, reused (they hold connection pools).
  Creating one per call is a real perf bug.
- `TypeAdapter` at module level to validate non-model types like
  `list[ContentBlock]` — building it is expensive, so don't rebuild per call.
- Two same-named classes from different packages (my `TextBlock` vs anthropic's
  `TextBlock`) can't be validated into each other — go through `.model_dump()` →
  dict → my model.

---

## Verified experiments (in traces/calls.jsonl)

- temperature=0 is **not** fully deterministic — [fill in what you observed + why].
- Same content in English vs an Indic language → different `input_tokens`
  [fill in the ratio]. Feeds Day 2 tokenizer work.
- `max_tokens=10` → stop_reason is `max_tokens`, not `end_turn`.
- Multi-turn conversation → `input_tokens` grows each turn (I resend history).
- Both providers round-trip a tool-call conversation correctly.

---

## Known limitations (deliberately deferred)

- `ToolResultBlock.content` is `str` only; real API also accepts image/block lists.
- Traces log **full** request bodies — will get large and contain user data.
  Production needs truncation + redaction. Fine for a dev tool; noted on purpose.
- `load_dotenv()` called inside `llm.py` — impure for a library module. Would move
  to an explicit config module in a real service.
- Model dispatch is by string prefix (`claude`/`gpt`). A `MODEL_REGISTRY` dict is
  the grown-up version.
- `extra` fields from providers (e.g. Anthropic's `citations`) are silently ignored.
  Could set `extra="forbid"` to be told when a provider adds a field.

---

## End-of-day checkpoint — can I do these cold?

- [ ] Explain the full lifecycle: my `Message` list → HTTP → response → my `Response`.
- [ ] Name every `stop_reason` value and what the loop should do about each.
- [ ] Explain why `Response.content` is a list, not a string.
- [ ] Explain why async matters even though the loop is sequential (3+ reasons).
- [ ] Explain the provider mapping losses in both directions.