# Day 11 — MCP Server (exposing retrieval to any editor)

**Goal:** Wrap the Day 10 `search_code` retrieval as an MCP server so it runs inside
Claude Code / Cursor — cited codebase answers without leaving the editor.

**Status:** Done. Python MCP server built, verified standalone via MCP Inspector, wired
into Claude Code, and producing cited + cross-referenced answers about a real codebase.

---

## What MCP is (the grounding)

MCP (Model Context Protocol) = a standard way for AI apps (Claude Code, Cursor, Claude
desktop) to discover and call external tools. Build a tool server once, any MCP client can
use it — instead of each app inventing its own plugin format. I'd consumed MCP before
(AI News Summarizer); this is the server side.

**The trust boundary (mandatory security thinking):** an MCP server is a tool surface OTHER
apps connect to. I control only my side, so I expose the MINIMUM: `search_code` (read-only)
and NOT shell/write_file. A code-reading tool has no business running commands. Decide the
surface before building it — same trust-boundary logic as Day 5/7.

---

## Build decision: Python server (not TypeScript)

Chose Python over TS. Reasoning: the point of the day is learning the PROTOCOL, not
language-juggling. A Python server calls my existing `CodeIndex` directly — zero glue, all
energy on MCP concepts. Trade-off: no TS/npm artifact (could publish to PyPI instead for
the equivalent). Resume line stays honest: "Python MCP server exposing code-retrieval
tools, runs in Claude Code/Cursor" — NOT "published to npm."

---

## The server (surprisingly small)

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("miniagent-codesearch")     # name shows up in the client UI

@mcp.tool()
def search_code(query: str) -> str:
    """Search the codebase... cite results as file:start-end."""
    return _get_index().search(query, k=5)  # formatted with citations

mcp.run()   # stdio transport
```

- **`@mcp.tool()`** ≈ my own Day 3 `@tool` — signature → schema, docstring → description
  the model reads. MCP just standardizes it across apps. Deep Day-3 understanding
  transferred directly.
- **`FastMCP`** handles all the protocol plumbing (handshake, tool discovery, message
  framing).

---

## Concept: stdio transport + the stdout rule

Default transport is **stdio** — the client LAUNCHES my server as a subprocess and talks
over stdin/stdout pipes. That's why there's no port/URL for local editor use: the editor
spawns the script.

> **Critical gotcha:** on stdio, stdout is RESERVED for MCP protocol messages. Any
> `print()` to stdout corrupts the stream and breaks the client. ALL logging must go to
> `sys.stderr`. Trips up everyone's first stdio server.

---

## Bug: the client controls the server lifecycle

First run returned "index not built" — `INDEX` was None. Cause: I built the index inside
`if __name__ == "__main__":`, but **`mcp dev` doesn't run `__main__`** — it imports my `mcp`
object and runs the server its own way, bypassing that block.

> **The MCP lesson:** the CLIENT controls the server's lifecycle. I don't get to run my
> main block first. Init must hook into the server lifecycle or happen at import/first-use.

**Fix (used):** lazy init — build the index on first `search_code` call, cache it. Simple,
works under `mcp dev` and real clients; first query is slow (indexes), rest fast.
**Proper alternative (noted):** `FastMCP(lifespan=...)` runs setup at server startup — the
architecturally correct place, first query stays fast. Knew it, chose lazy for simplicity.

**Config via env var:** moved the repo path to `MINIAGENT_REPO` env var, because MCP client
configs set ENV VARS for the server (can't pass sys.argv easily). Built it in before the
editor step — saved a rework.

---

## Test standalone BEFORE the editor (eval discipline)

`uv run mcp dev mcp_server.py` → launches server + MCP Inspector (web UI to list/call
tools by hand). Confirmed `search_code` appears and returns real cited chunks BEFORE
touching any editor. That isolation means: if the editor later can't see it, the problem is
the integration config, not the server.

---

## Editor integration (Claude Code)

Config tells the editor how to LAUNCH the server (it's the client, spawns my subprocess):
```json
{"mcpServers": {"miniagent-codesearch": {
  "command": "uv",
  "args": ["run","--directory","/abs/path/miniagent","python","mcp_server.py"],
  "env": {"MINIAGENT_REPO": "/tmp/flask/src/flask"}
}}}
```
- command+args = how to start it (ABSOLUTE path — editor isn't in my dir).
- env.MINIAGENT_REPO = which repo to index (why I used an env var).

**Result — the full loop closed:** asked Claude Code "how does Flask dispatch a request?"
It called search_code, got cited chunks, NOTICED they were truncated, ran sed/grep to read
the full bodies, cross-referenced 4 files, and produced a layered source-verified answer
(WSGI entry → routing at context push → full_dispatch wrapper → dispatch_request →
view_functions lookup). It even flagged that THIS checkout uses an explicit ctx param
differing from released Flask 3.x — a version discrepancy. My retrieval tool, feeding a
model reasoning carefully, inside my real editor.

---

## Known limitations / deferred
- Lazy init (first query slow) instead of lifespan startup — noted the proper way.
- Very large classes still produce coarse chunks (e.g. whole Flask class 110-1628) — method
  -level chunking would be finer.
- Index in memory, rebuilt when the server process starts — a real deployment persists it.
- Python server, not the TS/npm package originally planned — publish to PyPI for the
  equivalent artifact if wanted.

---

## Interview-ready answers

> **Q: What is MCP and why does it matter?**
> A standard protocol so AI apps (Claude Code, Cursor) can discover and call external tools
> without each inventing its own plugin format. Build a server once, any MCP client uses it.
> I built one exposing my code-retrieval tool — it runs inside my editor now.

> **Q: How does an MCP server communicate?**
> Local ones use stdio — the client launches the server as a subprocess and pipes JSON-RPC
> over stdin/stdout. The catch: stdout is reserved for the protocol, so all logging must go
> to stderr or you corrupt the stream. (HTTP transport exists for remote servers.)

> **Q: A bug you hit building it?**
> "Index not built" — I'd put initialization in the `__main__` block, but the MCP runtime
> imports the module and runs the server itself, skipping `__main__`. The client controls
> the lifecycle. Fixed with lazy init; the proper way is a lifespan startup hook.

> **Q: How did you think about security for the server?**
> An MCP server is a tool surface other apps connect to — a trust boundary. I exposed only
> the read-only search tool, never shell or file-write. A code-reader shouldn't be able to
> run commands. Same minimal-surface principle as my deployed HTTP endpoint.

---

## Gut check — can I answer cold?
- [ ] What does MCP standardize, and why build a server vs consume one?
- [ ] Why must logging go to stderr on a stdio server?
- [ ] Why did init in `__main__` fail — who controls the server lifecycle?
- [ ] Why config the repo path via env var, not argv?
- [ ] What's the trust boundary of an MCP server, and what did I expose (and not)?