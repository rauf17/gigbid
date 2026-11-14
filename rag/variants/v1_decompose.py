"""V1 Decompose Retriever Preset.

Executes [decompose, dense, merge]: breaks multi-faceted job postings into atomic technical
requirements, retrieves per requirement, and fuses results using Reciprocal Rank Fusion.
"""
from __future__ import annotations

from typing import Any

from rag.pipeline import ComposablePipelineRetriever


class V1DecomposeRetriever(ComposablePipelineRetriever):
    """Preset for Stage V1 Requirement Decomposition retrieval."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(stages=["decompose", "dense", "merge"], **kwargs)
