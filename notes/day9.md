# Day 9 — Hybrid Search, Reranking & Measuring Retrieval

**Goal:** Fix what chunking couldn't (Day 8) with hybrid search + reranking — and, above
all, MEASURE whether they actually help instead of adding them on faith.

**Status:** Done. Built a golden-set eval harness, BM25, RRF fusion, and reranking. Ran a
real experiment across 3 corpora. Landed a measured, non-obvious conclusion about when
these techniques help — and when they don't.

---

## What I built

```
src/miniagent/retrieval/
  golden.py       # GoldenCase: query + must_contain (the eval set)
  evaluate.py     # recall@1, recall@k, avg rank scorer
  code_chunker.py # ast-based structure-aware chunking (one chunk per func/class)
```
Plus BM25 keyword search, Reciprocal Rank Fusion, and a CrossEncoder reranker in the
experiment harness.

---

## The golden set (measure before you optimize)

A handful of queries paired with a `must_contain` substring = the answer phrase. Any
change gets a SCORE, not a gut feeling. This is the eval instinct — can't improve what you
don't measure.

- `must_contain` substring (not exact-chunk-ID) — robust to re-chunking; you care that a
  retrieved chunk CONTAINS the answer, not which chunk wins.
- Metric = **recall@k**: is the answer in the top-k? That's what matters for RAG — if it's
  in the top-k, the LLM can use it.

---

## Lesson 1: a metric everything passes tells you nothing

First run, vector-only, recall@3: **10/10.** Looked great. Was useless.

> recall@3 with substring matching is a LENIENT metric — "is the answer anywhere in the
> top 3?" hides ranking quality. A rank-3 chunk counts the same as rank-1. A 10/10 doesn't
> mean retrieval is perfect; it means the test can't tell good from great.

**Fix:** switch to **recall@1** (is it the TOP chunk?) + report **avg rank**. Instantly
revealing: vector-only dropped to **recall@1 6/10, avg rank 1.6**. NOW there's room to
measure improvement. (Also caught a print bug labeling both numbers "recall@1".)

> Lesson: if every approach passes your benchmark, tighten the benchmark before comparing
> approaches.

---

## The techniques

**BM25 (keyword).** Scores chunks by exact-word overlap, rare words weighted higher.
Catches exact identifiers embeddings blur (function names, error codes). Alone it's WEAKER
than vector (dumber about meaning) — the point is it succeeds/fails on DIFFERENT cases,
which is why fusion works.

**Reciprocal Rank Fusion (RRF).** Combines two rankings by RANK POSITION, not score
(cosine 0-1 and BM25 unbounded aren't comparable). Each system contributes
`1/(rrf_k + rank)`; a chunk high in EITHER gets a boost, high in BOTH gets the most.
`rrf_k=60` = standard damping constant.

**Reranking (cross-encoder).** Scores query + chunk TOGETHER (not two independent
embeddings), so it can "read" whether a chunk answers the query. Slow (runs per candidate)
→ retrieve wide (top-k cheap), rerank narrow (top-n accurate). Never rerank all chunks.

---

## The experiment: 3 corpora, 4 methods

### Corpus 1 — small prose doc (quorra_docs.md, 30 chunks)
| method | recall@1 | avg rank | note |
|---|---|---|---|
| vector | 6/10 | 1.6 | strong baseline |
| BM25 | 3/10 | 2.2 | weak alone; won exact-term cases |
| hybrid | 6/10 | 1.8 | fixed crash frag (rank 3→1); HURT semantic-only cases |
| rerank | 5/10 | — | no gain — retrieval already near ceiling at this scale |

**Finding:** hybrid tied vector; reranking didn't help. On small prose, plain vector wins.
BM25 noise on semantic-only queries (where it's blind) POLLUTED fusion and dragged good
vector rankings down.

### Corpus 2 — real code (Flask, 24 files) with the PROSE chunker
Everything failed: recall@20 = 2-3/8. **All methods near-zero.**

> When ALL methods score near-zero, the problem is upstream (data), not the ranker. Stop
> tuning, look at the chunks.

Two red herrings caught here (both instructive):
1. **First theory (WRONG): chunker shattered identifiers.** Checked — `def send_file` etc.
   WERE present in chunks. Disproved my own hypothesis with data.
2. **Actual cause #1: chunk INCOHERENCE.** The chunk containing `def send_file` was full
   of unrelated `flashes`/`session` code — the prose char-chunker splices adjacent-but-
   unrelated functions together. The identifier was present but its CONTEXT was polluted,
   so the embedding represented a muddle and matched no query.
3. **Actual cause #2 (the real one): a STALE `source` variable** in the test harness. The
   catastrophic 2/8 was largely a harness bug, not a retrieval bug.

> **Biggest lesson of the day:** a broken eval harness produces the SAME symptom as broken
> retrieval. Verify the harness before diagnosing the system. I chased chunker theory for
> an hour; the bug was a variable pointing at the wrong path.

### Corpus 3 — real code with AST structure-aware chunking (code_chunker.py)
`ast.parse` → one chunk per FunctionDef/ClassDef, with a header line
(`FunctionDef url_for in ...`) so the identifier is prominent. Coherent units, clean
embeddings, accurate line ranges for citations.

| method | recall@1 | avg rank | note |
|---|---|---|---|
| vector | 6/8 | 1.2 | strong |
| BM25 | 6/8 | 1.5 | |
| **hybrid** | **7/8** | 1.2 | **WON — only method to get `url_for` to rank 1** |
| rerank | 6/8 | 1.4 | still no gain at this scale |

**`url_for` was NEVER found with the prose chunker; with AST chunking hybrid got it to
rank 1.** recall@20 went 7/8 → 8/8.

---

## The conclusion (measured across 3 corpora — strong interview claim)

> Hybrid search + reranking are standard, but I measured that they do NOT automatically
> beat plain vector search. On small prose: no gain. On code with a prose chunker:
> everything failed — chunk INCOHERENCE capped retrieval regardless of ranker. On code
> with AST chunking: hybrid finally won (recall@1 7/8 vs 6/8) and uniquely ranked exact
> identifiers first. Hybrid pays off when TWO conditions both hold: coherent chunks AND
> exact-identifier queries. And the dominant factor everywhere is **chunk coherence, not
> ranking cleverness** — bad chunks (or a stale harness variable) tanked recall far more
> than any ranker choice ever moved it.

**Decision for Day 10:** the Codebase Q&A agent = AST chunking + hybrid retrieval (its
corpus is code, its queries are full of function names). Keep reranking + the harness for a
larger/noisier corpus — measure per corpus, don't assume.

---

## Bugs / fixes hit
- **Token-limit 400** — `chunk_python` had no size cap, so a huge ClassDef exceeded the
  embed model's 8192-token limit. Fix: cap unit size, split oversized units with the Day 8
  char-chunker, re-attach the header. (Char cap is approximate — the CORRECT fix is
  token-counting with tiktoken, which I built on Day 2. Nice callback.)
- **Embedding all 396 chunks in one call** — batch in 100s (rate limits + isolate which
  batch fails). Doesn't fix an oversized single chunk — the size cap does.
- **ast.walk double-counts nested defs** (a method chunk + its class chunk) — some
  duplication; acceptable for now, dedupe later.

---

## Interview-ready answers

> **Q: Does hybrid search / reranking improve RAG?**
> It depends, and I measured it on 3 corpora. On small prose, no — modern embeddings are
> strong. On code with coherent (AST) chunks and identifier queries, hybrid won and
> uniquely ranked exact identifiers first, because BM25 contributes exact-match signal
> vector blurs. Reranking needs larger scale to pay off. The dominant factor is chunk
> coherence, not the ranker.

> **Q: How do you evaluate retrieval?**
> A golden set of queries with known-correct answer phrases, scored on recall@1, recall@k,
> and average rank. I learned to distrust recall@k alone — my first metric was so lenient
> everything scored 10/10, which told me nothing. recall@1 + avg rank exposed the real
> differences.

> **Q: You saw all methods fail — how did you debug it?**
> When every method scores near-zero, it's a data/harness problem, not a ranker problem. I
> first blamed the chunker, then checked and found the identifiers WERE present — disproving
> my own theory. The real causes were chunk incoherence (prose chunker splicing unrelated
> functions) and a stale variable in my test harness. Lesson: a broken harness looks
> exactly like broken retrieval — verify it first.

> **Q: How do you chunk code vs prose?**
> Prose: sentence-boundary + overlap. Code: AST-based, one chunk per function/class, so
> chunks are coherent semantic units with accurate line ranges for citations. I measured
> that the prose chunker on code capped retrieval near zero regardless of ranking — chunk
> coherence dominates.

---

## Gut check — can I answer cold?
- [ ] Why did recall@3 = 10/10 tell me nothing? What did recall@1 reveal?
- [ ] Why does RRF fuse by rank, not score?
- [ ] When does hybrid beat vector? (two conditions)
- [ ] Why did all methods fail on code with the prose chunker?
- [ ] What's the difference between a broken ranker and a broken harness — and how do you tell?
- [ ] Why AST chunking for code, and what does the header line do?