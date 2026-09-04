from __future__ import annotations
import ast
from miniagent.retrieval.chunker import Chunk, chunk_text

MAX_CHARS = 6000   # rough proxy for staying under the token limit (see note)


def chunk_python(source_code: str, source: str) -> list[Chunk]:
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    lines = source_code.splitlines()
    chunks: list[Chunk] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = node.end_lineno or start
            body = "\n".join(lines[start - 1:end])
            header = f"{node.__class__.__name__} {node.name} in {source}"
            full = f"{header}\n{body}"

            if len(full) <= MAX_CHARS:
                chunks.append(Chunk(text=full, source=source,
                                    start_line=start, end_line=end))
            else:
                # too big — split this one unit into size-bounded pieces
                for sub in chunk_text(body, source, target_chars=MAX_CHARS,
                                      overlap_sentences=1):
                    # re-attach the header so the identifier stays prominent
                    sub.text = f"{header}\n{sub.text}"
                    sub.start_line = start   # approximate; the unit's range
                    sub.end_line = end
                    chunks.append(sub)
    return chunks