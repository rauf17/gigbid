# Pre-Registered Hypotheses: R&D Question B (Retrieval Pipeline)

**Date:** 2026-11-14

These hypotheses are pre-registered prior to running evaluations on the RAG retrieval pipeline variants (V1 through V4) against the 600-job deterministic synthetic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`).

---

### H1 (V2 hybrid)
BM25 over the job TEXT fused with dense via reciprocal rank fusion raises evidence Recall@5 over V0 by at least 8 points, mainly on jobs naming exact tools (Celery, dbt, pgvector).

<!-- Result line to be added post-evaluation -->

---

### H2 (V3 rerank)
A cross-encoder reranking the top 30 raises MRR and nDCG@10 over V2 more than it raises Recall@5; it costs more p95 latency than any other stage.

<!-- Result line to be added post-evaluation -->

---

### H3 (V1 decomposition)
One retrieval per extracted requirement helps most on jobs with 5+ requirements and does not help (or hurts) jobs with 3-4; it adds LLM cost per job.

<!-- Result line to be added post-evaluation -->

---

### H4 (V4 outcome-aware)
Boosting evidence that appears in won proposals will NOT improve gold-evidence Recall@5 (gold ignores outcomes); any benefit would only show in GigSim reply rate. Expected: neutral.

<!-- Result line to be added post-evaluation -->
