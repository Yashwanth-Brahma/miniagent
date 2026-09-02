# Day 8 — Retrieval Done Right (fixing naive RAG)

**Goal:** Fix the three retrieval failures measured on Day 2 — starting with the two that
chunking can address (boundary corruption, answer fragmentation) — and re-measure against
my own numbers.

**Status:** Done. Semantic + overlapping chunker built (with line tracking for future
citations). Boundary corruption fixed and verified. Fragmentation improved but not
eliminated — with a measured, honest explanation of why chunking alone can't finish the job.

---

## What I built

```
src/miniagent/retrieval/chunker.py   # Chunk model + boundary-aware, overlapping chunker
```

Fixes target the Day 2 findings:
- Day 2 failure #1 (chunk-boundary corruption) → semantic chunking
- Day 2 failure #2 (answer fragmentation) → overlap (partial fix — see finding)
- Day 2 failure #3 (vocabulary sensitivity) → needs hybrid search = Day 9

---

## The two ideas

**1. Break only at sentence boundaries.** Grow a chunk by adding WHOLE sentences until it
hits ~target_chars, then stop. Never cut mid-sentence. target_chars is a target, not a
hard cap — a chunk may slightly exceed it to finish the current sentence. A clean boundary
is worth a few extra chars. → fixes mid-word fragments.

**2. Overlap.** After emitting a chunk, step the index back by N sentences so the next
chunk repeats the tail of the previous one. That shared sentence lets an answer spanning a
boundary appear whole in at least one chunk. → helps fragmentation.

**3. Line tracking (for free).** Each sentence carries its source line; each chunk records
start_line/end_line. This is the citation data the Day 10 agent needs — built in now, cheap;
retrofitting later is painful.

---

## The infinite-loop bug (real engineering lesson)

First version looped forever — debug print showed "next chunk starts at sentence 256"
repeating endlessly.

**Cause:** on a chunk containing only `overlap_sentences` worth of content (common at the
end), the inner loop advanced i by 1, then `i -= overlap_sentences` pulled it back by 1 →
net progress ZERO. The chunk was the size of the overlap, so overlap cancelled progress.

**Fix:** make forward progress a hard INVARIANT, not an assumption.
```python
chunk_start = i                      # where THIS chunk began
# ... build chunk ...
next_start = i - overlap_sentences
if next_start <= chunk_start:        # overlap would stall or go backward
    next_start = chunk_start + 1     # force at least one sentence of progress
i = next_start
```

> **Lesson:** any loop that can step backward (overlap, retries, backtracking) needs a
> forward-progress invariant. My original `if i < 0` guard only caught NEGATIVE index — it
> missed the subtler "stuck in place" case. The real invariant isn't "i ≥ 0", it's "i
> strictly increases each chunk."

---

## Verified fixes

- **Boundary corruption: FIXED (by inspection).** Day 2 top chunk started mid-word
  (`"dles everything...depende"`). Day 8 chunks all start at real words / capital letters,
  quotable as-is.
- **Overlap: WORKING (by inspection).** CHUNK 0 END and CHUNK 1 START are the same
  sentence — the bridge that carries context across a boundary.

---

## The key finding: chunking helped, but can't fully fix fragmentation

Re-ran the Day 2 failure query ("what happens to accumulators after a crash?") at three
configs:

| config | top result |
|---|---|
| target=500, OL=1 | write-before-proceed setup, cut before the crash conclusion (partial) |
| target=800, OL=2 | drifted to "what a stateful transformation is" — WORSE (diluted) |
| target=300, OL=1 | answer conclusion at rank 1; supporting logic at rank 3 (best) |

**Why it can't be fully fixed by chunking:** the complete crash-recovery answer is ~5
sentences of connected reasoning (write-before-proceed → restore to exact value → resume →
ordering guarantee). No small chunk holds all of it; going bigger to capture it DILUTES the
embedding so it ranks worse.

> **The fundamental tradeoff (felt by turning the knobs, not read):**
> - Small chunks → precise embeddings, clean retrieval, but answers FRAGMENT across them.
> - Large chunks → answers stay together, but the embedding averages over too much and
>   ranks LOWER.
> Chunk size is a precision-vs-completeness dial with no single right value — it depends on
> how long your answers tend to be.

**Chosen working config: target=300, OL=1** — surfaced the answer conclusion at rank 1
(measured, not guessed).

### What actually finishes the job (sets up the week)
Chunking alone can't. The remaining two fixes:
1. **Retrieve top-k + let the LLM synthesize** (Day 10 agent) — don't need one perfect
   chunk; retrieve #1 AND #3, hand both to the model, it stitches the answer. This is WHY
   real RAG returns multiple chunks (first hit on Day 2, now with fresh evidence).
2. **Reranking** (Day 9) — score query + candidate TOGETHER (not just embedding
   similarity) to pull the most complete chunk up.

---

## Known limitations / deferred
- Sentence splitting is naive (splits on .!? + newlines) — mishandles "e.g.", "3.14",
  code. Fine for prose; real CODE retrieval needs structure-aware chunking (functions,
  classes).
- Small chunks (30 from 13KB) mean more overlap duplication — a knob to tune once measured.

---

## Interview-ready answers

> **Q: How do you chunk documents for RAG?**
> Break at sentence/paragraph boundaries, not fixed character counts, so chunks are never
> mid-word — and overlap consecutive chunks so an answer spanning a boundary survives. I
> track source line ranges per chunk for citations. I learned the hard way that overlap can
> infinite-loop if a chunk is smaller than the overlap — fixed with a forward-progress
> invariant.

> **Q: How do you pick chunk size?**
> It's a precision-vs-completeness tradeoff, and I measured it. Small chunks give precise
> embeddings but fragment long answers across chunks; large chunks keep answers together
> but dilute the embedding so it ranks lower. I tested 300/500/800 on a query whose answer
> spanned ~5 sentences — 300 surfaced the conclusion at rank 1. There's no universal
> value; it depends on answer length.

> **Q: If chunking can't fully fix fragmentation, what does?**
> Two things: retrieve top-k and let the LLM synthesize across chunks (which is why RAG
> returns multiple, not one), and reranking to pull the most complete candidate up. I
> measured that even good chunking left the answer split across rank 1 and rank 3 — so the
> fix is at the retrieval + synthesis layer, not just chunking.

---

## Gut check — can I answer cold?
- [ ] Why break at sentence boundaries instead of fixed chars?
- [ ] What does overlap fix, and how can it cause an infinite loop?
- [ ] What's the real loop invariant that prevents the stall?
- [ ] What's the precision-vs-completeness tradeoff in chunk size?
- [ ] Why can't chunking alone fix answer fragmentation? What does?