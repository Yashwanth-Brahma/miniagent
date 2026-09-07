from __future__ import annotations
from pathlib import Path
import numpy as np
from openai import OpenAI
from rank_bm25 import BM25Okapi

from miniagent.retrieval.chunker import Chunk
from miniagent.retrieval.code_chunker import chunk_python
from dotenv import load_dotenv
load_dotenv()

_client = OpenAI()


class CodeIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, bm25: BM25Okapi) -> None:
        self.chunks = chunks
        self.vectors = vectors
        self.bm25 = bm25

    @classmethod
    def build(cls, repo_path: str) -> CodeIndex:
        repo = Path(repo_path)
        chunks: list[Chunk] = []
        for f in repo.rglob("*.py"):
            try:
                chunks.extend(chunk_python(f.read_text(encoding="utf-8"),
                                           source=str(f.relative_to(repo))))
            except Exception:
                continue

        # embed in batches (Day 9 lesson)
        vectors = _embed_all([c.text for c in chunks])
        bm25 = BM25Okapi([c.text.lower().split() for c in chunks])
        print(f"[index] {len(chunks)} chunks from {repo_path}")
        return cls(chunks, vectors, bm25)

    def search(self, query: str, k: int = 5, rrf_k: int = 60) -> list[Chunk]:
        # vector ranking
        q = _client.embeddings.create(model="text-embedding-3-small",
                                      input=[query]).data[0].embedding
        q = np.array(q); q /= np.linalg.norm(q)
        normed = self.vectors / np.linalg.norm(self.vectors, axis=1, keepdims=True)
        vec_rank = list(np.argsort(normed @ q)[::-1])

        # keyword ranking
        bm_rank = list(np.argsort(self.bm25.get_scores(query.lower().split()))[::-1])

        # RRF fusion
        fused: dict[int, float] = {}
        for ranking in (vec_rank, bm_rank):
            for rank, idx in enumerate(ranking):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank)
        top = sorted(fused, key=lambda i: fused[i], reverse=True)[:k]
        return [self.chunks[i] for i in top]


def _embed_all(texts: list[str], batch: int = 100) -> np.ndarray:
    out = []
    for i in range(0, len(texts), batch):
        resp = _client.embeddings.create(model="text-embedding-3-small",
                                         input=texts[i:i + batch])
        out.extend(d.embedding for d in resp.data)
    return np.array(out)