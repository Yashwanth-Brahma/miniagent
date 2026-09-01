# Day 3 — Tool Calling & Schema Design

**Goal:** Give the agent hands. Turn a plain typed Python function into a tool the
model can call, with schemas derived automatically (never hand-written).

**Status:** Done. `@tool` registry, dispatcher, 3 tools (read_file, list_dir,
http_get), full tool round-trip against the real API, and a schema-quality experiment
with measured results.

---

## What I built

```
src/miniagent/tools/
  registry.py   # @tool decorator, schema generation, REGISTRY lookup table
  dispatch.py   # ToolUseBlock in -> run tool -> ToolResultBlock out (error-contained)
  (builtins)    # read_file, list_dir, http_get
```

**The mental model — a tool round trip:**
```
  model decides it needs a tool ──tool_use──> my dispatcher ──> the tool (real work)
                                                    │
  model gets final answer  <──tool_result──────────┘
```
Day 3 builds ONE round trip. Day 4 wraps it in a loop.

---

## Part 1 — Decorators (the mechanism behind @tool)

A decorator is just **a function that takes a function and returns a function.**
`@loud` above `def add` is sugar for `add = loud(add)`.

```python
def loud(fn):
    @functools.wraps(fn)              # <-- copies __name__/__doc__ from fn
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper
```

Key pieces:
- **`*args, **kwargs`** = "accept any arguments." `*` packs positional into a tuple,
  `**` packs keyword into a dict. `fn(*args, **kwargs)` unpacks them back out. Pack on
  the way in, unpack on the way out.
- **Closure** — `wrapper` is defined inside `loud`, so it permanently captures `fn`
  from that scope (same as JS closures). That's how it still knows `fn` later.
- **`@functools.wraps(fn)` is NOT optional for @tool.** Without it, `add.__name__`
  becomes `"wrapper"` and `add.__doc__` becomes `None` — because `add` literally *is*
  `wrapper` now. @tool needs the real name (tool name) and docstring (description), so
  this bug would break every tool.

> **Insight:** @tool doesn't change what the function *does*. It attaches a schema and
> registers the function. The wrapper just calls through.

---

## Part 2 — Schema generation from type hints (the key trick)

Never hand-write JSON schemas. Read the function's signature at runtime and let
Pydantic build the schema.

```python
sig = inspect.signature(fn)
fields = {}
for name, param in sig.parameters.items():
    default = ... if param.default is inspect.Parameter.empty else param.default
    fields[name] = (param.annotation, default)      # (type, default) tuples
model = create_model(fn.__name__, **fields)         # build a Pydantic model at runtime
schema = model.model_json_schema()                  # Pydantic emits JSON Schema
```

- **`inspect.signature`** reads parameters, type hints, and defaults at runtime.
- **`create_model`** builds a Pydantic model dynamically from `(type, default)` tuples.
- **`...` (Ellipsis)** is Pydantic's marker for "required, no default."
- **`inspect.Parameter.empty`** is the sentinel for "no default" (not None, because a
  param could legitimately default to None).

Pydantic handles every type mapping for free — verified:
- `str`        -> `{"type": "string"}`
- `list[str]`  -> `{"type": "array", "items": {"type": "string"}}`
- `int | None` -> `{"anyOf": [{"type": "integer"}, {"type": "null"}]}`

### Nullable vs optional (subtle, interview-worthy)
`int | None` with NO default is still in `"required"`. "Optional" means two things:
- **can be None** (`int | None`) — must provide it, but null is allowed
- **can be omitted** (has a default) — don't have to pass it at all
To be truly omittable: `x: int | None = None`.

### Descriptions do the real work
Types make a tool *callable*; descriptions make the model call it *correctly*.
- Tool description ← from `fn.__doc__` (the docstring)
- Parameter descriptions ← from `Annotated[str, Field(description="...")]`

Final tool-definition shape (exactly what Anthropic's `tools` param wants):
```python
{"name": fn.__name__, "description": docstring, "input_schema": model.model_json_schema()}
```

---

## Part 3 — The registry (string -> function bridge)

```python
REGISTRY: dict[str, Callable] = {}
REGISTRY[fn.__name__] = wrapper       # "read_file" -> the function
```

**Why:** the model responds with a *string* ("call the tool named 'read_file'"). The
registry turns that string back into the actual callable:
```python
fn = REGISTRY[name]        # look up by name
result = fn(**args)        # run it
```
Replaces a giant `if name == ... elif ...`. Every @tool auto-registers, so the
dispatcher never needs editing when I add tools.

---

## Part 4 — The dispatcher (error containment is the point)

Input: a `ToolUseBlock`. Output: a `ToolResultBlock`. Nothing crashes the agent.

```python
def dispatch(block):
    fn = REGISTRY.get(block.name)                     # .get -> None if missing (no crash)
    if fn is None:
        return ToolResultBlock(..., is_error=True,
            content=f"no tool named '{block.name}'. Available: {list(REGISTRY)}")
    try:
        result = fn(**block.input)                    # ** unpacks args dict
    except Exception as e:
        return ToolResultBlock(..., is_error=True, content=f"Error: {e!r}")
    return ToolResultBlock(tool_use_id=block.id, content=str(result), is_error=False)
```

Every failure becomes a **message the model can read**, never an exception that kills
the run. Verified all three paths return without crashing:
- happy path -> file content
- hallucinated tool name -> "no tool named X, available: [...]" + is_error
- missing required arg -> caught TypeError + is_error

The model reads `is_error` results and recovers on its own (retries, tries another
path). An agent that dies on one missing file is useless; one that says "that doesn't
exist, let me try another" is an agent.

> **Deferred:** arg validation currently relies on catching Python's TypeError, which
> gives Python-flavored messages. Better: validate args against the Pydantic schema
> *before* calling, for cleaner "field X required" messages.

---

## Part 5 — The three tools

- **read_file** — `max_bytes` cap (tool output becomes next-call input tokens!).
- **list_dir** — defaults path to ".", returns "DIR "/"FILE" prefixes so the model
  knows what it can recurse into.
- **http_get** — 4 guards: URL scheme check, `timeout=10.0` (never hang the agent),
  separate TimeoutException handling, `max_chars` truncation (cost + context safety).

> **Deferred:** tools are SYNC for now; http_get blocks the agent (the "sync poisons
> async" issue). Revisit for async/parallel tool execution on Day 6.

---

## Part 6 — Tool round trip is MULTI-CALL (key realization)

The model never runs tools. It only *asks*. One "tool use" = minimum 2 API calls:
```
call 1: ask -> stop_reason "tool_use" + ToolUseBlock
        (my code runs the tool via dispatch)
call 2: send tool_result back -> model reads it -> final answer (stop_reason "end_turn")
```

Between calls I append TWO things to history, in order:
1. the assistant's turn (with its tool_use blocks) — `resp.to_message()`
2. a user turn holding the tool_result blocks
Wrong order -> API 400 (the alternation rule from Day 1).

### Bugs / lessons hit for real
1. **`tools` must be passed on EVERY call, not just the first.** Forgot it on call 2 ->
   model confused. Classic first-tool-use bug.
2. **Tool output becomes next-call input tokens.** Call 2 cost ~4x call 1 because the
   file contents I fed back were now input. This is why read_file has max_bytes and why
   real agents truncate tool output.
3. **The description drove tool selection.** With 3 tools, the model picked list_dir for
   a directory question purely from the schema text — no code told it which to use.

---

## Part 7 — Schema-quality experiment (measured, interview-gold)

**Design:** planted a trap — the tool wants `severity="warn"` but natural language
says "warning". Same tool, same 6 prompts, only the parameter description changed. Ran
each variant; inspected `resp.tool_uses[0].input` (did NOT run the tool — only cared
how the model *called* it).

**Results:**
```
  terse     ("the severity")                              3/6
  detailed  ("must be exactly one of: debug,info,warn,error")  6/6
  examples  (detailed + "for warnings use severity='warn'")    6/6
```

**Which cases failed under terse:** `warn` (got "warning") and `info` (got
"informational"). The 3 that passed (error, debug, error) passed only because the
natural word HAPPENS to equal the valid value.

> **The lesson (causal, from my data):** a parameter description carries no weight when
> the obvious guess is right, and ALL the weight when the valid value diverges from what
> the user would naturally say. Enumerating valid values closed the gap entirely;
> examples added no measurable benefit *on this trap* (they might on a harder,
> arbitrary value like "W" — not claiming more than the data shows).

**Caveat:** small model + 6 cases = some run-to-run noise. For solid numbers, run 2-3x
or use ~10 cases. One run was enough to see the terse-vs-detailed effect clearly.

---

## Interview-ready answers

> **Q: How do you define tools for an LLM?**
> A typed Python function + a decorator that reads its signature via `inspect` and
> generates JSON Schema via Pydantic. No hand-written schemas — the type hints ARE the
> schema. Docstring becomes the tool description, `Annotated[..., Field(description=)]`
> becomes per-parameter descriptions.

> **Q: What happens when a tool fails?**
> It never crashes the agent. The dispatcher catches everything and returns an
> is_error tool_result with the error message. The model reads it and recovers. Same
> for hallucinated tool names — I return the list of real tools so it can correct.

> **Q: How many API calls does using a tool take?**
> Minimum two: one where the model asks (stop_reason tool_use), then my code runs the
> tool, then a second where the model reads the result and answers. That's why an agent
> needs a loop — to repeat until the model stops asking.

> **Q: Do tool descriptions actually matter?**
> Measured it. Planted a value mismatch (tool wants "warn", users say "warning"). Terse
> description scored 3/6, enumerating valid values scored 6/6. Descriptions matter most
> exactly where the valid value diverges from the natural word.

---

## Gut check — can I answer cold?
- [ ] What does @functools.wraps fix, and why does @tool need it?
- [ ] Why route through Pydantic instead of hand-mapping types to schema?
- [ ] Nullable vs optional — why is `int | None` still required?
- [ ] Why does the dispatcher return errors instead of raising?
- [ ] Why is a tool round trip minimum 2 API calls?
- [ ] Why did the terse description fail on "warn" but pass on "error"?