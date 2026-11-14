"""Composable Multi-Stage Retrieval Pipeline (AI-4016 Requirements B2, B4, B5).

Stages:
- dense: Qdrant dense vector search over experience pool.
- decompose: LLM-based requirement decomposition (2-8 atomic sub-queries).
- merge: Per-requirement dense retrieval fused via Reciprocal Rank Fusion.
- hybrid: Dense + BM25 text retrieval fused via RRF (k=60).
- rerank: Pairwise cross-encoder reranking over top candidates.
- outcome_boost: Historical proposal win-rate scoring boost.
"""
from __future__ import annotations

import logging
from typing import Any

from rag.index.bm25 import BM25Index
from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.retriever import EvidenceItem, Retriever
from rag.stages.base import DEFAULT_EXPERIENCE_TYPES
from rag.stages.decompose import DecomposeStage
from rag.stages.dense import DenseStage
from rag.stages.hybrid import HybridStage
from rag.stages.merge import MergeStage
from rag.stages.outcome_boost import OutcomeBoostStage
from rag.stages.rerank import RerankStage

logger = logging.getLogger(__name__)

NAMED_PIPELINE_PRESETS: dict[str, list[str]] = {
    "v0": ["dense"],
    "v0_naive": ["dense"],
    "v1": ["decompose", "dense", "merge"],
    "v1_decompose": ["decompose", "dense", "merge"],
    "v2": ["hybrid"],
    "v2_hybrid": ["hybrid"],
    "v3": ["hybrid", "rerank"],
    "v3_rerank": ["hybrid", "rerank"],
    "v4": ["hybrid", "rerank", "outcome_boost"],
    "v4_outcome": ["hybrid", "rerank", "outcome_boost"],
}


class ComposablePipelineRetriever(Retriever):
    """Executes arbitrary compositions of retrieval stages matching pipeline presets."""

    def __init__(
        self,
        stages: list[str] | str | None = None,
        persona: str | None = None,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        bm25_index: BM25Index | None = None,
        cross_encoder: Any | None = None,
        reranker_model: str | None = None,
        use_hash_embedder: bool = False,
        outcome_alpha: float = 0.2,
        rrf_k: int = 60,
        rerank_top_k: int = 30,
        model_override: Any | None = None,
        unfiltered: bool = False,
    ) -> None:
        if isinstance(stages, str):
            self.stages = NAMED_PIPELINE_PRESETS.get(stages, [stages])
        elif stages is not None:
            self.stages = list(stages)
        else:
            self.stages = ["dense"]

        self.default_persona = persona
        self.unfiltered = unfiltered
        self.outcome_alpha = outcome_alpha
        self.rrf_k = rrf_k
        self.rerank_top_k = rerank_top_k

        # Initialize shared components
        self.embedder = embedder or get_embedder(use_hash_embedder=use_hash_embedder)
        self._owned_store = vector_store is None
        self.vector_store = vector_store or VectorStore(
            dimension=self.embedder.dimension,
            embedder=self.embedder,
        )
        self.vector_store.validate_embedder(self.embedder)

        self.bm25_index = bm25_index or BM25Index()

        # Instantiate stage handlers
        self.dense_stage = DenseStage(
            embedder=self.embedder,
            vector_store=self.vector_store,
        )
        self.hybrid_stage = HybridStage(
            embedder=self.embedder,
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            rrf_k=self.rrf_k,
        )
        self.decompose_stage = DecomposeStage(model_override=model_override)
        self.merge_stage = MergeStage(
            embedder=self.embedder,
            vector_store=self.vector_store,
            rrf_k=self.rrf_k,
        )
        self.rerank_stage = RerankStage(
            model_name=reranker_model,
            cross_encoder=cross_encoder,
        )
        self.outcome_stage = OutcomeBoostStage(alpha=self.outcome_alpha)

    async def retrieve(
        self,
        query: str | list[str],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        query_text = " ".join(query) if isinstance(query, list) else str(query)
        if not query_text.strip():
            return []

        filter_dict = filters or {}
        target_persona = filter_dict.get("persona") or self.default_persona or "ai_ml"

        if self.unfiltered or filter_dict.get("unfiltered"):
            chunk_types = filter_dict.get("type") or filter_dict.get("types")
        else:
            chunk_types = filter_dict.get("type") or filter_dict.get("types") or DEFAULT_EXPERIENCE_TYPES

        # Pipeline execution logic
        stages_set = set(self.stages)

        # 1. Candidate generation stage
        if "decompose" in stages_set and "merge" in stages_set:
            requirements = self.decompose_stage.execute(query_text)
            candidates = self.merge_stage.execute(
                requirements=requirements,
                k=max(k, self.rerank_top_k) if ("rerank" in stages_set or "outcome_boost" in stages_set) else max(k, 15),
                persona=target_persona,
                chunk_types=chunk_types,
            )
        elif "hybrid" in stages_set:
            hybrid_fetch_k = self.rerank_top_k if ("rerank" in stages_set or "outcome_boost" in stages_set) else k
            candidates = self.hybrid_stage.execute(
                query=query_text,
                k=hybrid_fetch_k,
                persona=target_persona,
                chunk_types=chunk_types,
            )
        else:
            dense_fetch_k = self.rerank_top_k if ("rerank" in stages_set or "outcome_boost" in stages_set) else k
            candidates = self.dense_stage.execute(
                query=query_text,
                k=dense_fetch_k,
                persona=target_persona,
                chunk_types=chunk_types,
            )

        # 2. Rerank stage
        if "rerank" in stages_set:
            rerank_pool = self.rerank_top_k if "outcome_boost" in stages_set else k
            candidates = self.rerank_stage.execute(
                query=query_text,
                candidates=candidates,
                top_k=rerank_pool,
                rerank_pool_size=self.rerank_top_k,
            )

        # 3. Outcome boost stage
        if "outcome_boost" in stages_set:
            candidates = self.outcome_stage.execute(
                candidates=candidates,
                persona=target_persona,
                top_k=k,
            )

        return candidates[:k]

    def close(self) -> None:
        if self._owned_store:
            self.vector_store.close()
