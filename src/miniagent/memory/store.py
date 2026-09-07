from __future__ import annotations
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

_client = OpenAI()


class MemoryStore:
    def __init__(self) -> None:
        self.facts: list[str] = []
        self.vectors: np.ndarray | None = None

    def add(self, fact: str) -> None:
        """Store a fact/decision the agent may need to recall later."""
        vec = _client.embeddings.create(
            model="text-embedding-3-small", input=[fact]).data[0].embedding
        vec = np.array([vec])
        self.vectors = vec if self.vectors is None else np.vstack([self.vectors, vec])
        self.facts.append(fact)

    def recall(self, query: str, k: int = 3) -> list[str]:
        """Retrieve the most relevant stored facts for a query."""
        if not self.facts:
            return []
        q = _client.embeddings.create(
            model="text-embedding-3-small", input=[query]).data[0].embedding
        q = np.array(q); q /= np.linalg.norm(q)
        normed = self.vectors / np.linalg.norm(self.vectors, axis=1, keepdims=True)
        scores = normed @ q
        top = np.argsort(scores)[::-1][:k]
        return [self.facts[i] for i in top]