"""V2 Hybrid Retriever Preset.

Executes [hybrid]: combines dense semantic similarity and BM25 text retrieval over full job text
using Reciprocal Rank Fusion (k=60) over the verified experience pool.
"""
from __future__ import annotations

from typing import Any

from rag.pipeline import ComposablePipelineRetriever


class V2HybridRetriever(ComposablePipelineRetriever):
    """Preset for Stage V2 Hybrid Dense + BM25 retrieval."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(stages=["hybrid"], **kwargs)
