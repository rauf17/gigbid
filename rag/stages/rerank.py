"""Cross-encoder reranking stage scoring top candidate passages against query."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from rag.retriever import EvidenceItem

logger = logging.getLogger(__name__)

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "rerank_cache.json"

_MEM_CACHE: dict[str, float] = {}
_CACHE_LOADED = False


def _get_cache() -> dict[str, float]:
    global _MEM_CACHE, _CACHE_LOADED
    if not _CACHE_LOADED:
        if DEFAULT_CACHE_PATH.is_file():
            try:
                _MEM_CACHE = json.loads(DEFAULT_CACHE_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _MEM_CACHE = {}
        _CACHE_LOADED = True
    return _MEM_CACHE


def _save_cache() -> None:
    try:
        DEFAULT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CACHE_PATH.write_text(json.dumps(_MEM_CACHE), encoding="utf-8")
    except OSError:
        pass


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
        cache = _get_cache()

        # Build pair keys
        q_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
        keys: list[str] = []
        unseen_pairs: list[tuple[str, str]] = []
        unseen_keys: list[str] = []

        for item in pool:
            t_hash = hashlib.md5(item.text.encode("utf-8")).hexdigest()
            key = f"{q_hash}_{t_hash}"
            keys.append(key)
            if key not in cache:
                unseen_pairs.append((query, item.text))
                unseen_keys.append(key)

        try:
            if unseen_pairs:
                encoder = self._get_encoder()
                new_scores = encoder.predict(unseen_pairs, batch_size=32, show_progress_bar=False)
                for k, score in zip(unseen_keys, new_scores, strict=True):
                    cache[k] = float(score)
                _save_cache()

            scores = [cache[k] for k in keys]

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
