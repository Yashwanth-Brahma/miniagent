# Week 2 — Retrieval, MCP, Memory & Orchestration

**Deliverable:** a **Codebase Q&A Agent** — hybrid retrieval over a real repo, answers
with `file:line` citations, exposed as an MCP server so it runs inside Claude Code /
Cursor. Plus your first *deliberate* use of a framework (LangGraph), now that you know
what one hides.

**Builds directly on Week 1:** your `miniagent` client, tools, loop, and — importantly —
your Day 2 retrieval failure findings and the summarize-middle stub you left unfinished.

**Daily shape (8h):** build-first (skip the docs-first slog), ~5h build → 2h experiment
→ 1h write-up (`notes/dayN.md`). Same as Week 1.

**Guardrails:**
- LangGraph is now allowed — but only AFTER you've felt the problem it solves.
- Keep measuring: retrieval quality against a golden set, not vibes.
- Commit daily. Keep the notes discipline — it IS your interview prep.
- Security grounding stays mandatory on the MCP day (exposing tools = trust boundary).

**Resume payoff:** this week fills the projected-resume entries — "Codebase Q&A Agent —
hybrid retrieval + MCP" and "MCP server published to npm." By Friday they're real, not
aspirational.

---

## Day 8 — Retrieval done right (fix naive RAG)

*Directly fixes the 3 failure modes you documented on Day 2.*

**Build:**
- [ ] Semantic chunking — split on sentence/paragraph boundaries, not fixed 300 chars
  (fixes your Day 2 chunk-boundary corruption)
- [ ] Chunk overlap — each chunk carries context from its neighbors (fixes answer
  fragmentation)
- [ ] Embed + store chunks with metadata (source file, line range) for citations later
- [ ] Re-run your Day 2 failure queries against the NEW chunking

**Experiment:** the same 3 queries that broke on Day 2 — do they retrieve clean, complete
chunks now? Measure the before/after. This is your "I found the problem AND fixed it"
story, with numbers.

**Write-up:** semantic vs fixed chunking, overlap, and the measured improvement on your
own failure cases.

---

## Day 9 — Hybrid search + reranking

*Embeddings miss exact terms; keyword search misses meaning. Combine them.*

**Build:**
- [ ] BM25 keyword search (catches exact identifiers embeddings blur — function names,
  error codes)
- [ ] Combine BM25 + vector scores (reciprocal rank fusion is the standard, simple move)
- [ ] A reranking pass over the top-k candidates
- [ ] A small **golden set** — ~15 queries with known-correct chunks — to measure against

**Experiment:** vector-only vs hybrid vs hybrid+rerank, scored on the golden set. Which
queries does each approach get right? (Your Day 2 vocabulary-mismatch case is a perfect
test — hybrid should fix what embeddings alone couldn't.)

**Write-up:** why hybrid beats either alone, with your golden-set numbers.

---

## Day 10 — The Codebase Q&A Agent

*Wire retrieval into miniagent as a tool. This is the project.*

**Build:**
- [ ] Point the pipeline at a REAL repo (pick one you know — even miniagent itself)
- [ ] A `search_code` tool that returns chunks WITH `file:line` citations
- [ ] Register it with your Day 3 tool system; let your Day 4 loop drive it
- [ ] Answers must cite sources (`file.py:42-58`) — verifiable, not hallucinated

**Experiment:** ask it real questions about the repo. Do the citations actually point to
the right lines? (This is your model-eval instinct — verify the claim against source.)

**Write-up:** how retrieval-as-a-tool differs from stuffing everything in context; why
citations matter for trust.

---

## Day 11 — MCP server (your TypeScript moment)

*Expose the retrieval tools via MCP so the agent runs inside Claude Code / Cursor.*
*You've done MCP before (AI News Summarizer) — this plays to your strengths.*

**⚠ Security grounding first (mandatory, ~10 min):** an MCP server is a tool surface others
connect to — same trust-boundary thinking as Day 5 and Day 7's read-only deploy. Decide
what you expose before you build.

**Build:**
- [ ] An MCP server (TypeScript) exposing `search_code` + retrieval tools
- [ ] stdio transport (for local Claude Code / Cursor use)
- [ ] Test it live inside Claude Code or Cursor — your agent's retrieval, in a real editor
- [ ] Publish to npm (small, visible, credible — a projected-resume line made real)

**Write-up:** what MCP standardizes, building a server vs consuming one, the trust
boundary of an exposed tool surface.

---

## Day 12 — Memory

*Finish the summarize-middle stub from Day 2, then go beyond it.*

**Build:**
- [ ] Wire a REAL LLM summary into your Day 2 summarize-middle context strategy (it's been
  a stub — now make it work)
- [ ] Short-term: summarize old turns instead of dropping them
- [ ] Semantic memory: store facts/decisions the agent can retrieve later (reuse Day 8-9
  retrieval — memory is just retrieval over past conversation)
- [ ] Test on a long multi-turn session that would overflow context

**Experiment:** a conversation long enough to overflow — does summarization keep the task
on track where truncation (Day 2's correctness bug) would have lost it?

**Write-up:** memory types (short-term/episodic/semantic), and how memory is really
retrieval pointed at the past.

---

## Day 13 — LangGraph (adopt the framework, deliberately)

*The guardrail all of Week 1 was "no LangChain — that's Week 2." Now you know what a loop
IS. Rebuild it in LangGraph and articulate the trade.*

**Build:**
- [ ] Rebuild your agent loop as a LangGraph state graph
- [ ] Checkpointing (persist state between steps)
- [ ] Human-in-the-loop interrupts (compare to your Day 5 approval gate)
- [ ] A subgraph or conditional edge (something your hand-rolled loop didn't do cleanly)

**Experiment — the key one:** what does LangGraph give you that your from-scratch loop
didn't? What does it hide that you now know is there (the guards, the provider adapter)?
Write BOTH lists. This comparison is the interview gold — you're one of few who can speak
to both sides.

**Write-up:** your hand-rolled loop vs LangGraph — what the framework adds, what it
abstracts, when you'd choose each.

---

## Day 14 — Ship + write-up

**Build:**
- [ ] Deploy the Codebase Q&A Agent (you have the Day 7 Docker/FastAPI pattern)
- [ ] MCP server published + a short usage README
- [ ] Live demo URL

**Write (2h):**
- [ ] Blog post: "Why naive RAG fails — and what actually fixes it" — you have the Day 2
  failure data AND the Day 8-9 fixes with numbers. This writes itself.
- [ ] Post it. Update GitHub profile.

---

## End-of-week checkpoint — can I do these cold?

- [ ] Explain 3 ways naive retrieval fails and the specific fix for each (from my own data).
- [ ] Why hybrid search beats vector-only OR keyword-only — with golden-set numbers.
- [ ] What MCP standardizes, and the trust boundary of exposing a tool server.
- [ ] How memory is really retrieval over the past; when to summarize vs drop.
- [ ] What LangGraph gives me over a hand-rolled loop, and what it hides.

---

## Resume state after Week 2

Projected-resume entries that become REAL:
- "Codebase Q&A Agent — hybrid retrieval (BM25 + vector) + reranking, file:line citations"
- "Custom MCP server published to npm; runs inside Claude Code / Cursor"
- AI skills line gains: RAG, hybrid retrieval, reranking, MCP development, LangGraph,
  memory systems

Combined with Week 1's miniagent, that's two deployed agent projects with write-ups — the
point at which you start applying.

---

*Resource links intentionally omitted — you learn build-first now. When you hit a concept
(RRF, BM25, pgvector, LangGraph state graphs), grab the specific doc then, not before.*