# synthetic: true
"""RAG retrieval and verification pipeline."""
from dataclasses import dataclass

import numpy as np


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    similarity: float


class RetrievalPipeline:
    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def score_chunks(self, query_vec: list[float], index_vecs: list[list[float]]) -> list[int]:
        q = np.array(query_vec, dtype=np.float32)
        idx = np.array(index_vecs, dtype=np.float32)
        scores = np.dot(idx, q) / (np.linalg.norm(idx, axis=1) * np.linalg.norm(q) + 1e-8)
        return list(np.argsort(scores)[::-1][:self.top_k])
