# Day 2 — Tokens, Cost, Context, and Retrieval Failure Analysis

**Goal:** See what you're paying for (tokens + cost), decide what to keep when
context overflows, and produce firsthand evidence of why naive retrieval fails.

**Status:** Done. `tokens.py`, `cost.py`, `context.py` built. Retrieval experiment
produced 3 documented failure modes + 1 honest non-failure.

---

## What I built

```
src/miniagent/
  tokens.py    # count tokens: local (OpenAI) + API-based (Anthropic)
  cost.py      # pricing table, per-call + session spend, cost in traces
  context.py   # 3 budget strategies for when history overflows
```

Plus a throwaway `scratch_embed.py` that ran the retrieval experiment (deleted after).

**How the pieces connect:**

```
  a conversation ──> tokens.py ──> cost.py ──> running total (printed per call)
   (messages)        (count)      (→ rupees)

                          │
                          └──> context budget manager (reuses the counter
                                to decide what to keep / drop)

  embedding experiment = separate track (chunk → embed → cosine search → find failures)
```

---

## Part 1 — Token counting (`tokens.py`)

### The key asymmetry (interview point)

```
  OpenAI    →  count LOCALLY, instantly, free   (tiktoken library)
  Anthropic →  count via an API CALL            (no local library)
```

OpenAI open-sourced their tokenizer (`tiktoken`), so counting happens on your own
machine. Anthropic didn't ship an equivalent, so you ask their server. That's *why*
one function is sync+free and the other is `async` + costs a round-trip.

> **Q: How do you count tokens for each provider?**
> OpenAI's is local and free via tiktoken but approximate if you're sloppy — you have
> to add per-message overhead (role markers, separators) or you undercount. Anthropic's
> is a remote API call that's exact but async and costs a round-trip. Different
> engineering tradeoffs: local+approximate vs remote+exact.

### The overhead gotcha

Token count is NOT just the text. Each message carries invisible overhead — markers
telling the model "this is a user turn," separators, formatting. Count only the text
and you'll always be UNDER the real number.

```python
total = 0
for msg in messages:
    total += 4                        # per-message overhead
    for block in msg.content:
        if block.type == "text":
            total += len(encoding.encode(block.text))
total += 2                            # reply priming
```

**Result:** matched real `usage.input_tokens` within 5% for both providers. ✅

### Why non-English costs more tokens (interview gold)

The same sentence costs MORE tokens in Kannada/Hindi than English. Why: the
tokenizer's vocabulary was trained mostly on English, so English words are often 1
token while Indic-script words get split into many small pieces — sometimes ~1 token
per byte. Real cost + context-window penalty for non-English users.

---

## Part 2 — Cost (`cost.py`)

### The one concept: input vs output price split

Every model has TWO prices, not one:

```
  input tokens:   cheap
  output tokens:  4–5x more expensive
```

> **Q: How do you control agent cost?**
> Output tokens cost multiples more than input, so I optimize what the model
> *generates* before what it *reads*. That's why short outputs, prompt caching, and
> "don't make the model echo the whole document back" matter. I track input and output
> separately because they're priced separately.

### The math

*(tokens ÷ 1,000,000) × price-per-million*, done separately for input and output:

```python
input_cost  = (usage.input_tokens  / 1_000_000) * input_rate
output_cost = (usage.output_tokens / 1_000_000) * output_rate
```

Guard unknown models with `return 0.0` — don't crash a running agent because a model
isn't in the pricing table yet.

### Session spend tracking

Module-level `_session_spend` + `record_spend()` / `get_session_spend()`. Needs
`global _session_spend` to reassign (Python requires this to modify a module-level var,
otherwise it creates a throwaway local). Noted as a code smell — a real system uses a
proper accumulator object.

Wired into `complete()` so every call prints:
```
[cost] this call: $0.0003 | session: $0.0041
```
Watching the total tick up changes design instinct — you reach for Haiku by reflex.

### Gotcha: scientific notation in traces

`json.dumps` writes tiny floats as `5.4e-05` (= 0.000054, correct but ugly). Fixed by
storing as a fixed-decimal string: `f"{cost:.6f}"` → `"0.000054"`. Tradeoff: it's now a
string, so Day 6 aggregation needs `float(record["cost_usd"])` first.

---

## Part 3 — Context budget manager (`context.py`)

**Problem:** context windows are finite. A long agent run keeps appending messages
until history won't fit. Need a rule for what to throw away. No free lunch — dropping
anything loses info; the question is which loss hurts least.

### Three strategies

```
  1. truncate oldest      drop from the front  ──> ⚠ CORRECTNESS BUG
  2. sliding window       pin msg[0], drop middle-front  ──> the fix
  3. summarize middle     keep first + last, LLM-summarize middle  ──> stub (week 2)
```

### The correctness-bug lesson (interview gold)

Message 0 is usually the TASK ("refactor the auth module"). Truncate-from-front
eventually deletes it → the agent forgets what it's doing and produces confidently
wrong work.

> **This is a CORRECTNESS bug, not a quality tradeoff.**
> - Quality tradeoff = output gets a bit worse.
> - Correctness bug = agent forgets its objective and does the wrong thing silently.
>
> The fix: pin message 0 (the task/system prompt), drop from the middle instead. One
> change and the agent always remembers its goal — it only forgets the *middle* of its
> work, which is far less catastrophic. This is why real systems pin the system prompt.

**Proved it with a test:** forced a tight budget on a 30-message convo.
```
truncate kept the task?   False
sliding  kept the task?   True
```
Seeing the unsafe strategy literally lose the task is the lesson.

> **Q: How do you handle long agent runs that overflow context?**
> Never truncate blindly from the front — that can drop the task itself, which is a
> correctness failure, not just quality loss. Pin the task/system prompt, use a sliding
> window over the rest, and for very long runs summarize the dropped middle with an LLM
> so you keep the gist without the tokens.

---

## Part 4 — Why naive retrieval fails (firsthand evidence)

Built the crudest possible RAG to break it on purpose: chunk a doc every 300 chars
(no respect for sentences), embed with `text-embedding-3-small`, brute-force cosine
search with numpy. **The crudeness is the point.**

### How cosine search works

Embedding = text turned into a list of 1536 floats = its position in "meaning space."
Cosine similarity = how aligned two vectors are. Normalize to length 1, then dot
product = cosine (higher = more similar).

```python
q = q / np.linalg.norm(q)                                   # normalize query
normed = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
scores = normed @ q                                          # all dot products at once
top = np.argsort(scores)[::-1][:k]                           # top-k indices
```

`@` (matrix multiply) does all chunk-vs-query comparisons in one operation. **This is
what a vector DB does under the hood, minus the indexing tricks.**

### How to READ the scores (the meta-skill)

- **Absolute level:** ~0.33 is weak; 0.5+ is a decent match.
- **Spread:** if top results are clustered within ~0.06, the model can't tell them
  apart → ranking is essentially random.

### The failures (measured, not read)

**Mode 1 — vocabulary/vagueness sensitivity** ✅
```
  "how to set up?"            → 0.333, 0.272, 0.270   (low + clustered, scattered chunks)
  "how do I install binary?" → 0.528, 0.488, 0.462   (higher, correct chunk on top)
```
Same information need, ~0.2 score jump from word choice alone. "Set up" is a synonym
the doc never uses AND a generic phrase that weakly matches everything → no strong
signal to rank on. **Naive retrieval is brittle to phrasing.**

**Mode 2 — chunk-boundary corruption** ✅
```
  top hit (0.528): "dles everything required to run a node, so there are
                    no external runtime depende..."
```
The BEST match is a fragment sliced mid-word ("dles" = tail of "bundles",
"depende" = "dependencies" cut off). **High ranking ≠ usable content.** Even a correct
retrieval returns broken text unusable as LLM context. Cause: 300-char splitting
ignores word/sentence structure.

**Mode 3 — answer fragmentation** ✅ (most interview-valuable)
```
  "what happens to accumulators after a crash?"
  0.522: "...estored from storage to exactly the value... processing resumes"  (conclusion)
  0.515: "Without it, a recovering node could restore accumulators to..."      (diff point)
  0.490: "...estart. When a stateful transformation updates its accumulator..." (setup)
```
The full answer is ONE chain of reasoning (update → write-before-proceed → restore on
crash → resume). 300-char splitting scattered it across 3 chunks; NO single chunk holds
the complete answer. Retrieval surfaces pieces but can't stitch them.

> **This is WHY real RAG retrieves top-k, not top-1:** answers span chunks, so you pull
> several and let the LLM synthesize across them. The fix isn't just "chunk better" —
> it's retrieve-multiple + synthesize.

**Mode 4 — ranking instability** ⬜ (tested, did NOT reproduce — honest finding)
```
  clean:   "how does credential rotation work?"      → 0.605, grace-period chunk
  bloated: "um so i was just wondering if maybe..."  → 0.604, same chunk, same order
```
0.001 difference = float noise. Filler had ~zero effect. Embeddings were robust to
conversational padding.

### The sharp insight tying it together (interview gold)

> **Vagueness broke retrieval; verbosity didn't. They're different failures.**
> - Vagueness (mode 1) *removes signal* — "set up" gives nothing sharp to match → fatal.
> - Verbosity (mode 4) *adds noise around a strong signal* — "credential rotation" is a
>   clear concept that dominates the filler → survivable.
>
> Dense embeddings pool whole-sentence meaning, so a strong concept survives being
> buried in noise but a weak/generic query has nothing to find. Most people lump these
> into one "bad query" bucket; distinguishing them comes from the data.

### Fixes I now understand (week 2 — not yet built)

- **Semantic chunking** — split on sentence/paragraph boundaries, not fixed chars.
- **Chunk overlap** — each chunk carries context from its neighbors (fixes modes 2 & 3).
- **Hybrid search** — keyword (BM25) + vector, to catch exact terms embeddings miss.
- **Reranking** — a second-pass model reorders the top-k candidates.
- **Retrieve top-k + synthesize** — don't rely on any single chunk being complete.

---

## End-of-day gut check — can I answer these cold?

- [ ] Why does the same question retrieve worse when phrased vaguely?
      *(low + clustered scores = no strong signal to rank on)*
- [ ] Why is a high retrieval score not enough?
      *(mode 2 — right chunk can still be a broken mid-word fragment)*
- [ ] Why does real RAG retrieve top-k instead of top-1?
      *(mode 3 — answers span chunks; the model synthesizes across them)*
- [ ] Why is truncate-oldest a correctness bug, not a quality tradeoff?
      *(it silently drops the task in message 0; agent forgets its objective)*
- [ ] Why does non-English text cost more tokens?
      *(tokenizer vocab is English-heavy; Indic scripts split into many small tokens)*
- [ ] Why is output priced higher than input, and how does that change design?
      *(4–5x more expensive; optimize what the model generates first)*

---

## Known limitations / deferred

- Summarize-middle context strategy is a STUB — real LLM summary is week 2.
- Session spend uses a module-level global — code smell, would use an accumulator object.
- Cost stored as a string to avoid sci-notation — must `float()` before aggregating.
- Retrieval experiment used fixed-char chunking on purpose (to expose failures); no
  overlap, no semantic boundaries, no reranking yet.