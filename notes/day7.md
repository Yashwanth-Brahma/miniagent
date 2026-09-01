# Day 7 — Shipping: FastAPI, Docker, and the Deployed Surface

**Goal:** Turn the agent from a Python function into a deployable HTTP service, packaged
so it runs anywhere — plus the README and blog post that make it legible to others.

**Status:** Done. FastAPI server (3 endpoints), Dockerized and running in a container,
README, and blog post ("What Agent Frameworks Hide"). Live deploy deferred (image ready).

---

## What I built

```
src/miniagent/server.py   # FastAPI: /run, /health, /metrics
Dockerfile + .dockerignore
README.md                 # architecture, real metrics, limitations
blog_post.md              # "What Agent Frameworks Hide"
```

---

## Part 1 — FastAPI wrapper

Turns `run(task, ...)` (Python-only) into HTTP endpoints anyone can call.

```python
@app.post("/run")
async def run_agent(req: RunRequest):
    result = await run(req.task, model=req.model, max_steps=req.max_steps, max_cost=req.max_cost)
    return result          # AgentResult -> JSON automatically
```

**The payoff of a Day 4 decision:** because `run()` returns a structured `AgentResult`
(Pydantic model), FastAPI serializes it to JSON with ZERO extra code. output / stop_reason
/ steps / cost become the response for free. Returning a structured result instead of a
bare string paid off three days later.

Three endpoints, each earns its place:
- **/health** — trivial, but deploy platforms PING it to check the service is alive and
  decide whether to route traffic. First thing to hit to confirm the server is up.
- **/run** — the real one. Task in, AgentResult out.
- **/metrics** — p50/p95 over HTTP. Signals "operable service, not a toy."

Bonus: FastAPI auto-generates interactive Swagger docs at `/docs` — free, and a nice demo
artifact — because I used Pydantic models for the request/response.

---

## Part 2 — The deployed surface is a DIFFERENT trust boundary (key security decision)

The server imports ONLY the safe tools (`read_file`, `list_dir`, `http_get`) — NOT the
dangerous ones (`shell`, `write_file`, `sql_query`).

> **Why:** on Day 5, the "user" was me at a terminal. On a public URL, the "user" is
> anyone on the internet. Exposing `shell` on a public endpoint = handing the internet a
> command runner, hardened or not. A public endpoint changes the threat model, so I scoped
> the deployed tool surface to read-only.

This is the single most interview-worthy sentence of the day: "a public endpoint is a
different trust boundary than a local CLI, so I scoped the deployed tools to read-only."
Most candidates wouldn't think to say it.

---

## Part 3 — Docker (runs anywhere, not just my machine)

**Problem it solves:** the agent runs locally because MY machine has Python 3.12, uv, and
deps set up just so. A deploy platform doesn't. Docker packages the exact Python version +
deps + code into an image that runs identically anywhere. "Works on my machine" → "works
everywhere" because you ship the machine.

### Key Dockerfile decisions
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# split: install DEPENDENCIES first (cacheable), build the PACKAGE after
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
COPY quorra_docs.md ./
RUN uv sync --frozen --no-dev

CMD ["uv","run","uvicorn","miniagent.server:app","--host","0.0.0.0","--port","8000"]
```

- **Layer caching via ordering.** Docker caches layers; deps change rarely, code changes
  constantly. Install deps BEFORE copying `src/`, so a code edit reuses the cached
  dependency layer (rebuild in seconds, not minutes). `--no-install-project` installs deps
  without building my package (which needs the source that isn't copied yet); the second
  `uv sync` builds the package after `src/` is present. This split is required for a
  PACKAGE project.
- **`--host 0.0.0.0`** — critical. Inside a container, `localhost` = "only reachable from
  inside this container." `0.0.0.0` = "listen on all interfaces," which is what lets
  outside traffic in. Forget it and the deployed service is unreachable.
- **`--frozen --no-dev`** — install exactly the lock (reproducible), skip dev deps
  (pytest/ruff/mypy — not needed to RUN, only to develop). Smaller image.

### .dockerignore — a security line, not just tidiness
```
.venv/ __pycache__/ .git/ .env traces/ *.pyc .mypy_cache/ .ruff_cache/
```
`.env` is in there because **you never bake API keys into an image** — an image can be
pulled and inspected, keys and all. Keys are injected at RUNTIME as env vars:
```bash
docker run -p 8000:8000 -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" miniagent
```
- `-p 8000:8000` maps host port → container port.
- `-e KEY=...` injects the secret at runtime (how secrets get in without baking).

---

## Part 4 — Three build errors I debugged (the deployment war story)

Docker iteration = build fails, tells you the file it wanted, add it, rebuild. Converged
on a correct minimal image in three steps:

1. **`Expected a Python module at src/miniagent/__init__.py`** — I had DELETED
   `__init__.py`. That file marks a directory as an importable Python package; my whole
   project is the `miniagent` package (uv init --package), so every layer — local imports,
   Docker build — needs it. Coming from JS this is unintuitive (JS needs no marker file).
   Fix: `touch src/miniagent/__init__.py` (empty is fine — existence is the point).
2. **`failed to open /app/README.md`** — pyproject references README.md; the build needs
   it. Fix: copy README.md into the image (and it exists now).
3. Version warning (`uv-build<0.12` vs uv 0.12.8) — harmless; cleared by widening
   `[build-system] requires` to `<0.13.0` and `uv lock`.

> **Interview-usable:** "walk me through a deployment issue" → the __init__.py story. Shows
> I understand Python packaging + Docker's file-by-file build model, and that I debug by
> reading the actual error rather than guessing.

**Verified:** container runs with none of my local setup — `/health` → ok, `/run` executed
a real task reading the container's own filesystem. "Runs anywhere" proven.

---

## Part 5 — README + blog post (legibility = job-hunt value)

- **README** — architecture diagram, module table, measured p50/p95, and (most important)
  a "Limitations & known trade-offs" section listing what the system does NOT do (injection
  mitigated-not-solved, cost-guard overshoot, exact-match loop detection, sync responses).
  Naming limitations makes a reader trust everything else. Same eval-honesty instinct,
  applied to my own docs.
- **Blog post** — "What Agent Frameworks Hide," angle: build-from-scratch reveals what the
  40-line tutorial buries (the loop guards, the lossy provider adapter, schema-from-type-
  hints, tool results as untrusted input). Frames each hard part of the week as a
  revelation. This is the shareable artifact that pulls recruiters TO the repo.

---

## Interview-ready answers

> **Q: How did you deploy your agent?**
> FastAPI wrapper exposing /run, /health, /metrics; the AgentResult model serializes to
> JSON for free. Containerized with Docker — deps installed in a separate cached layer from
> the package build, keys injected at runtime not baked into the image, server bound to
> 0.0.0.0 so container traffic reaches it. The image runs with none of my local setup.

> **Q: What changes when an agent goes from local to a public endpoint?**
> The trust boundary. Locally the user is me; publicly it's anyone with the URL. So I only
> registered the read-only tools on the server — shell/write_file/sql aren't exposed.
> Exposing a command runner on a public URL is handing out a shell, hardened or not.

> **Q: Walk me through a deployment problem you hit.**
> Docker build failed with "expected a module at __init__.py" — I'd deleted it. That file
> marks the directory as an importable package, which every layer depends on. Then it
> wanted README.md (referenced by pyproject). Both fixed by reading the exact error and
> copying/creating the file it named. Taught me Python's package model and Docker's
> file-by-file build.

> **Q: Why the two `uv sync` steps in your Dockerfile?**
> Layer caching. The first installs dependencies only (--no-install-project) so that layer
> is cached and reused when only my code changes; the second builds my package after the
> source is copied. Deps rarely change, code always does — this makes rebuilds fast.

---

## Known limitations / deferred
- **Live deploy not done** — image is ready; Railway/Fly.io is mostly platform setup.
- **Responses are synchronous** — production would stream step updates over SSE.
- No auth on the endpoints — fine for a scoped read-only demo, not for real use.

---

## Gut check — can I answer cold?
- [ ] Why does AgentResult make the API almost free?
- [ ] Why is the deployed tool surface read-only? What changed from local?
- [ ] Why split the Dockerfile into two uv sync steps?
- [ ] Why --host 0.0.0.0 and not localhost in a container?
- [ ] Why is .env in .dockerignore, and how do keys get into the container?
- [ ] What does __init__.py do, and why did deleting it break the build?
```