"""RAG retrieval variants package."""
from rag.variants.v0_naive import V0NaiveRetriever
from rag.variants.v1_decompose import V1DecomposeRetriever
from rag.variants.v2_hybrid import V2HybridRetriever
from rag.variants.v3_rerank import V3RerankRetriever
from rag.variants.v4_outcome import V4OutcomeRetriever

__all__ = [
    "V0NaiveRetriever",
    "V1DecomposeRetriever",
    "V2HybridRetriever",
    "V3RerankRetriever",
    "V4OutcomeRetriever",
]
