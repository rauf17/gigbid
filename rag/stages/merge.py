"""Merge stage fusing per-requirement dense retrieval results via Reciprocal Rank Fusion."""
from __future__ import annotations

from typing import Any

from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.retriever import EvidenceItem
from rag.stages.base import DEFAULT_EXPERIENCE_TYPES, compute_rrf_scores, roll_up_to_item_id


class MergeStage:
    """Executes dense retrieval per atomic requirement and merges results with RRF."""

    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        use_hash_embedder: bool = False,
        rrf_k: int = 60,
    ) -> None:
        self.embedder = embedder or get_embedder(use_hash_embedder=use_hash_embedder)
        self.vector_store = vector_store or VectorStore(
            dimension=self.embedder.dimension,
            embedder=self.embedder,
        )
        self.rrf_k = rrf_k

    def execute(
        self,
        requirements: list[str],
        k: int = 15,
        persona: str | None = None,
        chunk_types: list[str] | None = None,
    ) -> list[EvidenceItem]:
        target_types = chunk_types or DEFAULT_EXPERIENCE_TYPES
        per_req_ranked_lists: list[list[str]] = []
        item_objects: dict[str, Any] = {}

        for req in requirements:
            q_vec = self.embedder.embed_query(req)
            hits = self.vector_store.search(
                query_vector=q_vec,
                limit=k * 2,
                persona=persona,
                chunk_type=target_types,
            )

            req_list: list[str] = []
            for chunk, score in hits:
                item_id = roll_up_to_item_id(chunk.id)
                if item_id not in req_list:
                    req_list.append(item_id)
                    if item_id not in item_objects:
                        item_objects[item_id] = (chunk, float(score))

            if req_list:
                per_req_ranked_lists.append(req_list)

        if not per_req_ranked_lists:
            return []

        rrf_scores = compute_rrf_scores(
            ranked_lists=per_req_ranked_lists,
            k=self.rrf_k,
        )

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

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
