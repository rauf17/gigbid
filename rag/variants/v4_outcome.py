"""V4 Outcome-Aware Retriever Preset.

Executes [hybrid, rerank, outcome_boost]: boosts evidence items backed by empirical win rates
in historical won/replied proposals with configurable alpha smoothing.
"""
from __future__ import annotations

from typing import Any

from rag.pipeline import ComposablePipelineRetriever


class V4OutcomeRetriever(ComposablePipelineRetriever):
    """Preset for Stage V4 Outcome-Aware retrieval."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(stages=["hybrid", "rerank", "outcome_boost"], **kwargs)
