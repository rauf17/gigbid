"""V0 Naive Baseline Retriever.

Top-k cosine similarity over the entire job posting text against fixed chunks.
Serves as the benchmark baseline for RAG ablation experiments.
"""
from __future__ import annotations

from typing import Any

from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.retriever import EvidenceItem, Retriever


class V0NaiveRetriever(Retriever):
    """Baseline RAG retriever using direct dense cosine similarity over raw query text."""

    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        persona: str | None = None,
        use_hash_embedder: bool = False,
    ) -> None:
        self.embedder = embedder or get_embedder(use_hash_embedder=use_hash_embedder)
        self._owned_store = vector_store is None
        self.vector_store = vector_store or VectorStore(dimension=self.embedder.dimension)
        self.default_persona = persona

    async def retrieve(
        self,
        query: str | list[str],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        # Form single query string from input (top-k of whole text)
        query_text = " ".join(query) if isinstance(query, list) else str(query)
        if not query_text.strip():
            return []

        # Dense query vector
        query_vector = self.embedder.embed_query(query_text)

        # Parse filters
        filter_dict = filters or {}
        target_persona = filter_dict.get("persona") or self.default_persona
        target_type = filter_dict.get("type")
        target_skills = filter_dict.get("skills")
        target_outcome = filter_dict.get("outcome")

        # Dense search in Qdrant
        hits = self.vector_store.search(
            query_vector=query_vector,
            limit=k,
            persona=target_persona,
            chunk_type=target_type,
            skills=target_skills,
            outcome=target_outcome,
        )

        items: list[EvidenceItem] = []
        for chunk, score in hits:
            items.append(
                EvidenceItem(
                    id=chunk.id,
                    type=chunk.type,
                    source=chunk.source_path,
                    project=chunk.project,
                    date=chunk.date,
                    outcome=chunk.outcome,
                    text=chunk.text,
                    score=float(score),
                    skills=chunk.skills,
                )
            )
        return items

    def close(self) -> None:
        if self._owned_store:
            self.vector_store.close()
