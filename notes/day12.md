# Day 12 — Memory (and a live security vulnerability I found in my own agent)

**Goal:** Give the agent memory — finish the Day 2 summarize-middle stub, add semantic
memory, and wire it into the loop. Ended up also discovering a real security hole.

**Status:** Done. Real LLM summarization (closes the Day 2 stub), a semantic memory store
(= retrieval pointed at the past), memory wired into the agent — AND found+fixed a
credential-leak vulnerability in read_file.

---

## What I built

```
src/miniagent/memory/summarize.py   # real LLM summarization (was a Day 2 stub)
src/miniagent/memory/store.py       # MemoryStore: add() + recall() = embed + search
```

**The mental model — two kinds of memory, one problem (finite context window):**
- **Short-term (summarize):** compress old turns into an LLM summary. Keeps the FLOW.
- **Semantic (retrieve):** store facts, search them on demand. Recalls a SPECIFIC fact.

> **Key insight:** semantic memory IS retrieval, pointed at the past. recall() is literally
> my Day 2 cosine_search renamed; add() is the embedding step. I didn't build a memory
> system — I reused my RAG stack over conversation instead of code.

---

## Part 1 — Finishing the Day 2 summarize stub

Day 2 left: `summary = "[TODO: real LLM summary]"`. Now it's a real model call.

The crux is the PROMPT — it's the memory policy:
```
"Summarize... Preserve: what the user wanted, key decisions/findings, and any facts the
agent will need later. Drop pleasantries and redundancy."
```
A naive "summarize this" loses the task + constraints — the exact Day 2 correctness bug.
Instructing what to PRESERVE keeps the load-bearing content.

Still **pins message 0** (the task) — summarization compresses the MIDDLE, never the task.
Both Day 2 lessons combine: pin the task (correctness) AND summarize the middle
(compression) instead of dropping it (quality).

**Tested it:** long convo with a task + scattered constraints. Summary output:
> "User wants to refactor auth.py from Flask sessions to JWT, keeping the legacy endpoint
> on sessions. Auth is in auth.py, secret key in config.py, session setup at line 40."

Preserved the task, the `/legacy` constraint, and the key facts; dropped the filler.

> **Why this matters:** the `/legacy` constraint survived. Truncation would drop it if it
> fell out of the window, and the agent would later break /legacy without knowing it was a
> requirement. Measured: summarization preserves constraints truncation discards.

---

## Part 2 — Semantic memory (retrieval over the past)

```python
class MemoryStore:
    def add(self, fact):      # embed + append
    def recall(self, query, k=3):   # cosine search = Day 2 cosine_search, renamed
```
Tested: "where's the secret key?" → config.py fact at rank 1; "what should I not migrate?"
→ /legacy constraint at rank 1 (matched by MEANING — "not migrate" ≈ "keep using sessions,
not JWT", almost no word overlap). Semantic recall works.

---

## Part 3 — Wiring memory into the agent

recall() only RETURNS facts — sending them to the model is a separate design decision.
Pattern used: recall on the task, inject into the system prompt before the loop runs.

**Proved memory changes behavior:** "what should I not migrate to JWT?" → the agent
recalled the /legacy constraint from memory and answered correctly in 1 STEP, without
searching the code. A fact from the past steered a present decision. ✓

### Design decisions noted (simple version built, better versions noted)
- **When to recall:** automatic (every turn) vs memory-as-a-TOOL (agent decides, using my
  Day 3 @tool). Tool version is cleaner + token-efficient — memory becomes just another
  registered tool. Built automatic; noted the tool version.
- **How many facts — SCORE THRESHOLD (important):** top-k returns k even when fewer are
  relevant. The secret-key query recalled 3 facts including irrelevant ones ("prefers
  TypeScript"), and injecting all of them sent the agent WANDERING (6 steps). Same "top-k
  returns k even when only 1 is good" issue from Day 9 — now causing real misbehavior. Fix:
  only inject facts above a similarity threshold.
- **What to store:** manual add() for now; production needs an extraction step (an LLM call
  that pulls "durable facts worth remembering" from each exchange). Noted, not built.

---

## 🚨 Part 4 — The security vulnerability I found (headline lesson)

While testing the secret-key query, the agent found `.env`, read it, and **printed my real
Anthropic + OpenAI API keys in plaintext.** Rotated both keys immediately.

**What happened:** the task was innocent ("where's the secret key?"). Memory pointed at
config.py. The agent wandered to `.env` via read_file and dumped the contents.

**This is the lethal trifecta (Day 5) firing on my own machine:**
- secret access (read_file can read .env)  +  output channel (returned it verbatim)
- = exfiltration. Here to my screen; with http_get it'd be to an attacker.

**The gap in my own code:** on Day 5 I hardened WRITE_FILE with a path jail, but left
READ_FILE completely open — it'll read .env, .git, SSH keys, anything. A code-QA agent
should NEVER read secrets.

**The fix — capability removal (same principle as read-only SQL on Day 5):**
```python
BLOCKED = {".env", ".git", "id_rsa", "credentials"}
# read_file refuses paths matching secrets, .pem/.key suffixes, etc.
```
Denylist on read_file so a code-reader physically can't touch credentials. Capability
removal beats output-scrubbing — don't let it read the file at all.

> **The lesson:** I secured the obvious dangerous tool (write) and left the "safe-looking"
> one (read) wide open. Reading is dangerous too when the data is sensitive. Every tool
> that touches the filesystem needs a security review, not just the ones that obviously
> mutate state. Found it through normal use — the task "succeeded" but did something it
> never should have.

---

## Known limitations / deferred
- Memory injection is automatic + unfiltered — needs a score threshold (noted, bit me).
- No fact-extraction step — facts added manually.
- MemoryStore is in-memory, not persisted across sessions.
- read_file denylist is a start; a fuller version would sandbox the readable root too.

---

## Interview-ready answers

> **Q: How do you give an agent memory?**
> Two mechanisms for two problems. Summarization compresses old turns into an LLM summary
> to keep the conversation's flow in the window — with a prompt that explicitly preserves
> the task and constraints, because naive summarizing drops exactly what matters. And a
> semantic store for recalling specific facts on demand — which is just retrieval pointed at
> the past, so I reused my RAG stack. recall() is my cosine search renamed.

> **Q: What's the hard part of agent memory?**
> Relevance, not storage. Top-k recall returns k facts even when only one is relevant —
> injecting the noise sent my agent wandering. You need a score threshold. And deciding
> WHAT to store is genuinely hard — production needs a fact-extraction step.

> **Q: A security bug you found in your own work?**
> Testing memory, my code-QA agent read my .env and printed my API keys. The lethal
> trifecta on my own machine — secret access plus an output channel. I'd path-jailed
> write_file on day 5 but left read_file open; reading is dangerous too when the data is
> sensitive. Fixed with a denylist — capability removal, same as my read-only SQL
> connection. Rotated the keys. The task "succeeded" while doing something it never should
> have — which is why you test by using it, not just by passing checks.

---

## Gut check — can I answer cold?
- [ ] Why does the summarizer prompt specify what to PRESERVE, not just "summarize"?
- [ ] Why is semantic memory "just retrieval pointed at the past"?
- [ ] Why did injecting top-k memories make the agent wander? What's the fix?
- [ ] What's the difference between summarization memory and semantic memory — when each?
- [ ] Why was read_file a security hole when write_file was already hardened?
- [ ] How does the .env leak map to the lethal trifecta?