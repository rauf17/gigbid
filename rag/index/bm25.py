"""BM25 sparse lexical index using rank-bm25 with payload filtering."""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from rag.schema import Chunk

DEFAULT_BM25_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "index" / "bm25.pkl"


def tokenize_text(text: str) -> list[str]:
    """Simple alphanumeric tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


class BM25Index:
    """Manages BM25 index over persona chunks with payload filtering."""

    def __init__(self, index_path: Path | str | None = None) -> None:
        self.index_path = Path(index_path or DEFAULT_BM25_PATH)
        self.chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None

        if self.index_path.is_file():
            self.load(self.index_path)

    def build(self, chunks: list[Chunk]) -> None:
        """Constructs BM25 index from a collection of chunks."""
        self.chunks = list(chunks)
        tokenized_corpus = [tokenize_text(c.text) for c in self.chunks]
        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
        else:
            self._bm25 = None

    def save(self, path: Path | str | None = None) -> None:
        """Serializes the index and chunks to disk."""
        target = Path(path or self.index_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "chunks": [c.model_dump() for c in self.chunks],
        }
        with open(target, "wb") as f:
            pickle.dump(data, f)

    def load(self, path: Path | str) -> None:
        """Loads chunks and re-initializes BM25 from disk."""
        target = Path(path)
        if not target.is_file():
            return
        with open(target, "rb") as f:
            data = pickle.load(f)
        raw_chunks = data.get("chunks", [])
        self.chunks = [Chunk.model_validate(c) for c in raw_chunks]
        tokenized_corpus = [tokenize_text(c.text) for c in self.chunks]
        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
        else:
            self._bm25 = None

    def search(
        self,
        query: str,
        limit: int = 5,
        k: int | None = None,
        persona: str | None = None,
        chunk_type: str | None = None,
        skills: list[str] | str | None = None,
        outcome: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Scores chunks against query and applies metadata filters."""
        if not self._bm25 or not self.chunks:
            return []

        actual_limit = k if k is not None else limit
        f = filters or {}
        p = persona or f.get("persona")
        t = chunk_type or f.get("type")
        o = outcome or f.get("outcome")
        s = skills or f.get("skills")

        query_tokens = tokenize_text(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        filtered_results: list[tuple[Chunk, float]] = []
        for chunk, score in zip(self.chunks, scores, strict=True):
            if score <= 0.0:
                continue

            # Apply filters
            if p and chunk.persona != p:
                continue
            if t and chunk.type != t:
                continue
            if o and chunk.outcome != o:
                continue
            if s:
                # Skill intersection check
                skill_list = [s] if isinstance(s, str) else list(s)
                chunk_skills_lower = {x.lower() for x in chunk.skills}
                target_skills_lower = {x.lower() for x in skill_list}
                if not chunk_skills_lower.intersection(target_skills_lower):
                    continue

            filtered_results.append((chunk, float(score)))

        filtered_results.sort(key=lambda x: x[1], reverse=True)
        return filtered_results[:actual_limit]
