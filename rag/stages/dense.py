"""Dense retrieval stage using Qdrant vector store with experience type filtering."""
from __future__ import annotations

from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.retriever import EvidenceItem
from rag.stages.base import DEFAULT_EXPERIENCE_TYPES, roll_up_to_item_id


class DenseStage:
    """Retrieves candidates using dense vector similarity over the experience pool."""

    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        use_hash_embedder: bool = False,
    ) -> None:
        self.embedder = embedder or get_embedder(use_hash_embedder=use_hash_embedder)
        self.vector_store = vector_store or VectorStore(
            dimension=self.embedder.dimension,
            embedder=self.embedder,
        )

    def execute(
        self,
        query: str,
        k: int = 15,
        persona: str | None = None,
        chunk_types: list[str] | None = None,
    ) -> list[EvidenceItem]:
        target_types = chunk_types or DEFAULT_EXPERIENCE_TYPES
        query_vector = self.embedder.embed_query(query)

        hits = self.vector_store.search(
            query_vector=query_vector,
            limit=k * 2,
            persona=persona,
            chunk_type=target_types,
        )

        seen_items: set[str] = set()
        items: list[EvidenceItem] = []

        for chunk, score in hits:
            item_id = roll_up_to_item_id(chunk.id)
            if item_id not in seen_items:
                seen_items.add(item_id)
                items.append(
                    EvidenceItem(
                        id=item_id,
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
            if len(items) >= k:
                break

        return items
