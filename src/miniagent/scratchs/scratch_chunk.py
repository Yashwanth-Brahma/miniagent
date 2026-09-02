# scratch_chunk.py
from pathlib import Path
from miniagent.retrieval.chunker import chunk_text

text = Path("./quorra_docs.md").read_text()
print(f"Text length: {len(text)}\n")
chunks = chunk_text(text, source="quorra_docs.md", target_chars=500, overlap_sentences=1)

print(f"{len(chunks)} chunks\n")
print("CHUNK 0 END:", chunks[0].text[-80:])
print("CHUNK 1 START:", chunks[1].text[:80])
# for c in chunks[:2]:
#     print(f"[lines {c.start_line}-{c.end_line}]  {c.text}...")
#     print("---")