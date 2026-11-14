"""V3 Rerank Retriever Preset.

Executes [hybrid, rerank]: retrieves top-30 candidates with hybrid search and reranks them
using a pairwise Cross-Encoder down to the final top-10.
"""
from __future__ import annotations

from typing import Any

from rag.pipeline import ComposablePipelineRetriever


class V3RerankRetriever(ComposablePipelineRetriever):
    """Preset for Stage V3 Cross-Encoder Reranking retrieval."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(stages=["hybrid", "rerank"], **kwargs)
