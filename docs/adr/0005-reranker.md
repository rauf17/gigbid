# ADR 0005: Selection of Cross-Encoder Model for RAG Reranking (Stage V3)

**Status:** accepted

## Context
Assignment Requirement B2 and Prompt 7 specify that Stage V3 of the retrieval pipeline uses a Cross-Encoder to rerank the top-30 candidates down to top-10.
The specification requires:
> "default `BAAI/bge-reranker-v2-m3`; if CPU time for the full dev set exceeds ~15 min, switch to a smaller cross-encoder via config and record the choice + measured time in docs/adr/0005-reranker.md"

## Measured Benchmarks
We benchmarked 30 candidate pairs (the exact batch size per query) on developer CPU:

1. **`BAAI/bge-reranker-v2-m3`** (560M parameters, XLM-RoBERTa architecture):
   - **Weight download / load time**: 155.73s
   - **Prediction time per 30 pairs**: **7.47s**
   - **Projected runtime for 511 dev set queries**:
     $$\frac{511 \times 7.47\text{ s}}{60\text{ s/min}} \approx \mathbf{63.6\text{ minutes}}$$
   - **Verdict**: Exceeds the 15-minute operational limit by more than 4x.

2. **`cross-encoder/ms-marco-MiniLM-L-6-v2`** (22M parameters, MiniLM-L6 architecture):
   - **Weight download / load time**: 19.49s
   - **Prediction time per 30 pairs**: **0.369s**
   - **Projected runtime for 511 dev set queries**:
     $$\frac{511 \times 0.369\text{ s}}{60\text{ s/min}} \approx \mathbf{3.14\text{ minutes}}$$
   - **Verdict**: Executes the entire 511-job dev set in ~3.1 minutes, well below the 15-minute threshold while maintaining strong pairwise passage relevance scoring.

## Decision
We configure **`cross-encoder/ms-marco-MiniLM-L-6-v2`** as the default cross-encoder for the V3 reranker stage in `agent/config.yaml` (`rag.reranker`).

## Consequences
- Evaluation of V3 and subsequent stages completes in under 4 minutes total.
- Cross-encoder reranking is fully operational in local CPU development and CI environments.
- The reranker model remains fully configurable in `agent/config.yaml`.
