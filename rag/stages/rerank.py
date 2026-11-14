"""Cross-encoder reranking stage scoring top candidate passages against query."""
from __future__ import annotations

import logging
from typing import Any

from rag.retriever import EvidenceItem

logger = logging.getLogger(__name__)

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankStage:
    """Reranks candidate evidence items using a pairwise Cross-Encoder model."""

    def __init__(
        self,
        model_name: str | None = None,
        cross_encoder: Any | None = None,
    ) -> None:
        self.model_name = model_name or DEFAULT_RERANKER_MODEL
        self._cross_encoder = cross_encoder

    def _get_encoder(self) -> Any:
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder

            self._cross_encoder = CrossEncoder(self.model_name, max_length=256)
        return self._cross_encoder

    def execute(
        self,
        query: str,
        candidates: list[EvidenceItem],
        top_k: int = 10,
        rerank_pool_size: int = 30,
    ) -> list[EvidenceItem]:
        if not candidates:
            return []

        pool = candidates[:rerank_pool_size]
        pairs = [(query, item.text) for item in pool]

        try:
            encoder = self._get_encoder()
            scores = encoder.predict(pairs, batch_size=32)

            scored_candidates: list[EvidenceItem] = []
            for item, score in zip(pool, scores, strict=True):
                scored_candidates.append(
                    EvidenceItem(
                        id=item.id,
                        type=item.type,
                        source=item.source,
                        project=item.project,
                        date=item.date,
                        outcome=item.outcome,
                        text=item.text,
                        score=float(score),
                        skills=item.skills,
                    )
                )

            scored_candidates.sort(key=lambda x: x.score, reverse=True)
            return scored_candidates[:top_k]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[rerank] Cross-encoder reranking failed: %s. Returning raw pool.", exc)
            return pool[:top_k]
