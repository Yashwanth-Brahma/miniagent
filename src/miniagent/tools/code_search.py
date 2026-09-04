from miniagent.tools.registry import tool
from miniagent.retrieval.index import CodeIndex

_INDEX: CodeIndex | None = None   # set once at startup

def set_index(index: CodeIndex) -> None:
    global _INDEX
    _INDEX = index


@tool
def search_code(query: str) -> str:
    """Search the indexed codebase for relevant code. Returns code snippets WITH their
    file path and line numbers, which you MUST cite in your answer as file:start-end."""
    print(f"[search_code] query={query!r}")
    if _INDEX is None:
        return "Error: no codebase indexed."
    results = _INDEX.search(query, k=5)
    if not results:
        return "No relevant code found."
    parts = []
    for c in results:
        citation = f"{c.source}:{c.start_line}-{c.end_line}"
        parts.append(f"--- {citation} ---\n{c.text[:800]}")
    return "\n\n".join(parts)