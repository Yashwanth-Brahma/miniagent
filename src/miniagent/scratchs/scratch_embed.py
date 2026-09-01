from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

text = Path("src/miniagent/test.md").read_text()

def chunk(text: str, size: int = 300) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]

chunks = chunk(text)
print(f"{len(chunks)} chunks")

from openai import OpenAI
import numpy as np

client = OpenAI()

def embed(texts: list[str]) -> np.ndarray:
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return np.array([d.embedding for d in resp.data])

chunk_vecs = embed(chunks)   # shape: (n_chunks, 1536)
print(chunk_vecs.shape)

def cosine_search(query: str, chunk_vecs: np.ndarray, chunks: list[str], k: int = 3):
    q = embed([query])[0]                              # (1536,)
    # normalize to unit length so dot product = cosine
    q = q / np.linalg.norm(q)
    normed = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
    scores = normed @ q                                # (n_chunks,) — one score per chunk
    top = np.argsort(scores)[::-1][:k]                 # indices of the k highest
    return [(scores[i], chunks[i]) for i in top]

for score, ch in cosine_search("how does credential rotation work?", chunk_vecs, chunks):
    print(f"{score:.3f}  {ch[:100]}")