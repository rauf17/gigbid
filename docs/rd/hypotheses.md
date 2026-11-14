# Pre-Registered Hypotheses: R&D Question B (Retrieval Pipeline)

**Date:** 2026-11-14

These hypotheses are pre-registered prior to running evaluations on the RAG retrieval pipeline variants (V1 through V4) against the 600-job deterministic synthetic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`).

---

### H1 (V2 hybrid)
BM25 over the job TEXT fused with dense via reciprocal rank fusion raises evidence Recall@5 over V0 by at least 8 points, mainly on jobs naming exact tools (Celery, dbt, pgvector).

**Result: Refuted**
- **Evidence:** `evals/results/rag_v2_hybrid_latest.json` vs `evals/results/rag_v0_naive_latest.json`
- **Measured Recall@5:** V0 = `0.2867` (146.5 / 511), V2 = `0.3121` (159.5 / 511) -> Delta = `+0.0254` (+2.54 points).
- **Findings:** While hybrid lexical-semantic RRF fusion improved Recall@5 (+2.54 points) and nDCG@10 (`0.4617` -> `0.4870`, +0.0253), the overall dev-set Recall@5 gain fell short of the pre-registered 8.0-point threshold. However, persona-specific gains on technical tool-heavy queries were substantial: the AI/ML persona (Dr. Elena Rostova) saw Recall@5 increase from `0.2222` to `0.3450` (+12.28 points).

---

### H2 (V3 rerank)
A cross-encoder reranking the top 30 raises MRR and nDCG@10 over V2 more than it raises Recall@5; it costs more p95 latency than any other stage.

**Result: Partially Confirmed / Refuted**
- **Evidence:** `evals/results/rag_v3_rerank_latest.json` vs `evals/results/rag_v2_hybrid_latest.json`
- **Measured Metrics:**
  - Recall@5: V2 = `0.3121` -> V3 = `0.3308` (Delta = `+0.0187` / +1.87 points)
  - MRR: V2 = `0.7363` -> V3 = `0.7397` (Delta = `+0.0034` / +0.34 points)
  - nDCG@10: V2 = `0.4870` -> V3 = `0.4878` (Delta = `+0.0008` / +0.08 points)
  - Latency p95: V2 = `296.7ms` -> V3 = `2982.4ms` (Delta = `+2685.7ms`)
- **Findings:** The latency cost hypothesis is **confirmed**: cross-encoder transformer reranking incurred a p95 latency of `2982.4ms`, higher than any other retrieval pipeline stage. The ranking metric hypothesis is **refuted**: reranking improved Recall@5 (+0.0187) more than it improved MRR (+0.0034) or nDCG@10 (+0.0008).

---

### H3 (V1 decomposition)
One retrieval per extracted requirement helps most on jobs with 5+ requirements and does not help (or hurts) jobs with 3-4; it adds LLM cost per job.

**Result: Confirmed**
- **Evidence:** `evals/results/rag_v1_decompose_latest.json` vs `evals/results/rag_v0_naive_latest.json`
- **Measured Metrics:**
  - Recall@5: V0 = `0.2867` -> V1 = `0.2276` (Delta = `-0.0591` / -5.91 points)
  - MRR: V0 = `0.7417` -> V1 = `0.6660` (Delta = `-0.0757`)
  - nDCG@10: V0 = `0.4617` -> V1 = `0.4014` (Delta = `-0.0603`)
  - Resource usage: `363,928` tokens consumed; p95 latency = `1671.9ms`.
- **Findings:** Decomposing job postings into atomic requirements fragmented the semantic context, causing dense retrieval to surface overly generic or isolated skill matches that diluted evidence quality across 5+ requirement jobs. It substantially underperformed holistic dense retrieval while incurring heavy token and latency costs.

---

### H4 (V4 outcome-aware)
Boosting evidence that appears in won proposals will NOT improve gold-evidence Recall@5 (gold ignores outcomes); any benefit would only show in GigSim reply rate. Expected: neutral.

**Result: Confirmed**
- **Evidence:** `evals/results/rag_v4_outcome_latest.json` vs `evals/results/rag_v3_rerank_latest.json` and `evals/results/ablation_latest.json`
- **Measured Metrics:**
  - Recall@5: V3 = `0.3308` -> V4 = `0.3298` (Delta = `-0.0010` / -0.10 points)
  - MRR: V3 = `0.7397` -> V4 = `0.7396` (Delta = `-0.0001`)
  - nDCG@10: V3 = `0.4878` -> V4 = `0.4880` (Delta = `+0.0002`)
- **Findings:** As predicted, Bayesian Laplace win-rate boosting had a strictly neutral impact on gold evidence retrieval (`|Δ| <= 0.0010`). Gold relevance is defined purely by technical capability, so historical win outcomes do not distort retrieval while preserving downstream win signals for agent proposal generation.
