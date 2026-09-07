from mcp.server.mcpserver import MCPServer
from miniagent.retrieval.index import CodeIndex
import os

# create the server — the name is what shows up in Claude Code/Cursor
mcp = MCPServer("miniagent-codesearch")

# build the index ONCE at startup (indexing per-query would be absurd)
INDEX: CodeIndex | None = None
REPO_PATH = os.environ.get("MINIAGENT_REPO", "/tmp/flask/src/flask")


def _get_index() -> CodeIndex:
    global INDEX
    if INDEX is None:
        INDEX = CodeIndex.build(REPO_PATH)   # built once, on first search
    return INDEX

@mcp.tool()
def search_code(query: str) -> str:
    """Search the indexed codebase for relevant code. Returns snippets with their
    file path and line numbers. Cite them as file:start-end in your answer."""
    index = _get_index()
    results = index.search(query, k=5)
    if not results:
        return "No relevant code found."
    parts = []
    for c in results:
        citation = f"{c.source}:{c.start_line}-{c.end_line}"
        parts.append(f"--- {citation} ---\n{c.text[:800]}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    mcp.run()   # runs on stdio by default