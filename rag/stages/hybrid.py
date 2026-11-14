"""Hybrid dense + BM25 text retrieval stage fused with Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations

from typing import Any

from rag.index.bm25 import BM25Index
from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.retriever import EvidenceItem
from rag.stages.base import DEFAULT_EXPERIENCE_TYPES, compute_rrf_scores, roll_up_to_item_id


class HybridStage:
    """Executes dense + BM25 over job text, fusing ranked lists using RRF."""

    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        bm25_index: BM25Index | None = None,
        use_hash_embedder: bool = False,
        rrf_k: int = 60,
    ) -> None:
        self.embedder = embedder or get_embedder(use_hash_embedder=use_hash_embedder)
        self.vector_store = vector_store or VectorStore(
            dimension=self.embedder.dimension,
            embedder=self.embedder,
        )
        self.bm25_index = bm25_index or BM25Index()
        self.rrf_k = rrf_k

    def execute(
        self,
        query: str,
        k: int = 30,
        persona: str | None = None,
        chunk_types: list[str] | None = None,
    ) -> list[EvidenceItem]:
        target_types = chunk_types or DEFAULT_EXPERIENCE_TYPES
        fetch_limit = max(k * 2, 40)

        # 1. Dense retrieval
        query_vector = self.embedder.embed_query(query)
        dense_hits = self.vector_store.search(
            query_vector=query_vector,
            limit=fetch_limit,
            persona=persona,
            chunk_type=target_types,
        )

        dense_ranked_items: list[str] = []
        item_objects: dict[str, Any] = {}
        for chunk, score in dense_hits:
            item_id = roll_up_to_item_id(chunk.id)
            if item_id not in dense_ranked_items:
                dense_ranked_items.append(item_id)
                item_objects[item_id] = (chunk, float(score))

        # 2. BM25 text retrieval over full job text
        bm25_hits = self.bm25_index.search(
            query=query,
            k=fetch_limit,
            persona=persona,
            chunk_type=target_types,
        )

        bm25_ranked_items: list[str] = []
        for chunk, score in bm25_hits:
            item_id = roll_up_to_item_id(chunk.id)
            if item_id not in bm25_ranked_items:
                bm25_ranked_items.append(item_id)
                if item_id not in item_objects:
                    item_objects[item_id] = (chunk, float(score))

        # 3. Reciprocal Rank Fusion
        rrf_scores = compute_rrf_scores(
            ranked_lists=[dense_ranked_items, bm25_ranked_items],
            k=self.rrf_k,
        )

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 4. Construct ranked EvidenceItems
        result: list[EvidenceItem] = []
        for item_id, rrf_score in sorted_items[:k]:
            chunk, _ = item_objects[item_id]
            result.append(
                EvidenceItem(
                    id=item_id,
                    type=chunk.type,
                    source=chunk.source_path,
                    project=chunk.project,
                    date=chunk.date,
                    outcome=chunk.outcome,
                    text=chunk.text,
                    score=float(rrf_score),
                    skills=chunk.skills,
                )
            )

        return result
