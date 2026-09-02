from pathlib import Path
import numpy as np
from openai import OpenAI
from miniagent.retrieval.chunker import chunk_text
from dotenv import load_dotenv
load_dotenv()

client = OpenAI()
text = Path("quorra_docs.md").read_text()
chunks = chunk_text(text, source="quorra_docs.md", target_chars=300, overlap_sentences=1)

def embed(texts):
    r = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return np.array([d.embedding for d in r.data])

chunk_vecs = embed([c.text for c in chunks])

def search(query, k=3):
    q = embed([query])[0]; q = q / np.linalg.norm(q)
    normed = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
    scores = normed @ q
    top = np.argsort(scores)[::-1][:k]
    return [(scores[i], chunks[i]) for i in top]

# THE Day 2 failure case
for score, c in search("what happens to accumulators after a crash?"):
    print(f"{score:.3f}  [lines {c.start_line}-{c.end_line}]")
    print(f"       {c.text[:160]}")
    print("---")