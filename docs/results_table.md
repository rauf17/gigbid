# GigBid Evaluation Results Table

This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Hybrid BM25+Dense, V2 Multi-Representation) and downstream decision runners.

> [!NOTE]
> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).
> Metrics are automatically updated by running `make eval` or `uv run python scripts/results_table.py`.

---

### Overall Retrieval Performance

| Variant | Recall@5 | MRR | nDCG@10 | Queries | Embedder | Dataset SHA | Commit |
|:---|:---:|:---:|:---:|:---:|:---|:---:|:---:|
| `v0_naive` | **0.0397** | **0.0961** | **0.0520** | 600 | `bge-small-en-v1.5` | `6d1d7813` | `55984e9` |

---

### Performance by Freelancer Persona

| Variant | Persona | Queries | Recall@5 | MRR | nDCG@10 |
|:---|:---|:---:|:---:|:---:|:---:|
| `v0_naive` | AI/ML (Dr. Elena Rostova) | 200 | 0.0356 | 0.0803 | 0.0448 |
| `v0_naive` | Full-Stack Web (Marcus Vance) | 200 | 0.0344 | 0.1061 | 0.0506 |
| `v0_naive` | Data Analysis (Amina Al-Mansoor) | 200 | 0.0490 | 0.1019 | 0.0606 |

---

### Performance by Requirement Complexity (`n_requirements`)

| Variant | Requirements | Queries | Recall@5 | MRR | nDCG@10 |
|:---|:---:|:---:|:---:|:---:|:---:|
| `v0_naive` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 3-4 skills | 408 | 0.0309 | 0.0756 | 0.0419 |
| `v0_naive` | 5+ skills | 192 | 0.0582 | 0.1396 | 0.0736 |
