# ADR 0003: Choice of Embedding Model and Deterministic Test Embedder

**Status:** accepted

## Context
GigBid requires local, high-speed dense vector retrieval to match client job posting requirements against synthetic freelancer portfolios (CV, case studies, repositories, reviews, and past proposals).

The embedding model must satisfy:
1. Fast CPU inference without requiring a dedicated GPU.
2. Low embedding dimension to maintain minimal memory footprint in local Qdrant storage.
3. Top-tier retrieval ranking on MTEB benchmarks.
4. Deterministic, zero-network test execution for CI pipelines.

## Decision
1. **Production Embedding Model**: `BAAI/bge-small-en-v1.5` via `sentence-transformers`:
   - **Dimension**: 384 dimensions (lightweight compared to 1536-dim or 1024-dim alternatives).
   - **Performance**: High MTEB retrieval performance in the small model class.
   - **Inference Speed**: Highly optimized for CPU inference on commodity developer laptops and standard Linux runners.
   - **Configuration**: Configurable via `agent/config.yaml` (`profiles.open.embeddings`).

2. **Deterministic Offline Test Embedder (`HashEmbedder`)**:
   - Implemented in `rag/index/embeddings.py`.
   - Projects token hashes into a deterministic 384-dimensional unit vector using md5 feature hashing and L2 normalization.
   - Requires zero network requests and zero model downloads.
   - Enforced across unit and integration tests (`USE_HASH_EMBEDDER=1`) to guarantee hermetic CI builds.

## Consequences
- Fast local indexing (`< 3s` for entire persona corpus).
- Offline unit and integration tests pass reliably without network dependencies or flaky model weight downloads.
- Transparent migration path: other models can be configured in `agent/config.yaml` without codebase refactoring.
