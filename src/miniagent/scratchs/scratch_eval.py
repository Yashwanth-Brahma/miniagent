from pathlib import Path
import numpy as np
from openai import OpenAI
from miniagent.retrieval.chunker import chunk_text
from miniagent.retrieval.code_chunker import chunk_python
from miniagent.retrieval.evaluate import score
from dotenv import load_dotenv
load_dotenv()

client = OpenAI()
REPO = Path("/tmp/flask/src")
files = list(REPO.rglob("*.py"))
print(f"{len(files)} python files")

chunks = []
for f in files:
    try:
        text = f.read_text(encoding="utf-8")
    except Exception:
        continue
    # keep the file path relative, for citations + so you know where chunks came from
    rel = str(f.relative_to(REPO.parent))
    chunks.extend(chunk_python(text, source=rel))

def embed_all(texts, batch=100):
    vecs = []
    for i in range(0, len(texts), batch):
        resp = client.embeddings.create(model="text-embedding-3-small",
                                        input=texts[i:i + batch])
        vecs.extend(d.embedding for d in resp.data)
    return np.array(vecs)

chunk_vecs = embed_all([c.text for c in chunks])

def vector_search(query, k=3): # k is how many results to return
    q = client.embeddings.create(model="text-embedding-3-small", input=[query]).data[0].embedding
    q = np.array(q); 
    q /= np.linalg.norm(q)
    normed = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
    top = np.argsort(normed @ q)[::-1][:k]
    return [chunks[i] for i in top]

print("=== VECTOR ONLY ===")
score(vector_search, k=20)

from rank_bm25 import BM25Okapi

# BM25 works on tokenized text — crude whitespace tokenization is fine to start
tokenized = [c.text.lower().split() for c in chunks]
bm25 = BM25Okapi(tokenized)

def keyword_search(query, k=3):
    scores = bm25.get_scores(query.lower().split())
    top = np.argsort(scores)[::-1][:k]
    return [chunks[i] for i in top]

print("=== KEYWORD (BM25) ONLY ===")
score(keyword_search, k=20)

def reciprocal_rank_fusion(query, k=5, rrf_k=60):
    # get a ranked list of chunk indices from each system
    q_vec = client.embeddings.create(model="text-embedding-3-small", input=[query]).data[0].embedding
    q_vec = np.array(q_vec); q_vec /= np.linalg.norm(q_vec)
    normed = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
    vec_rank = list(np.argsort(normed @ q_vec)[::-1])

    bm_scores = bm25.get_scores(query.lower().split())
    bm_rank = list(np.argsort(bm_scores)[::-1])

    # RRF: each system contributes 1/(rrf_k + rank) for each chunk
    fused: dict[int, float] = {}
    for ranking in (vec_rank, bm_rank):
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank)

    top = sorted(fused, key=lambda i: fused[i], reverse=True)[:k]
    return [chunks[i] for i in top]

print("=== HYBRID (RRF) ===")
score(reciprocal_rank_fusion, k=20)

from sentence_transformers import CrossEncoder
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_search(query, k=5, retrieve_n=8):
    candidates = reciprocal_rank_fusion(query, k=retrieve_n)
    pairs = [(query, c.text) for c in candidates]
    scores = reranker.predict(pairs)
    order = np.argsort(scores)[::-1][:k]
    return [candidates[i] for i in order]

print("=== RERANKED (CrossEncoder) ===")
score(rerank_search, k=20)