# GigBid Evaluation Results Table

This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Hybrid BM25+Dense, V2 Multi-Representation) and downstream decision runners.

> [!NOTE]
> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).
> Metrics are automatically updated by running `make eval` or `uv run python scripts/results_table.py`.

---

### Overall Retrieval Performance

| Variant | Recall@5 | R@5 Ceiling | MRR | nDCG@10 | Queries | Embedder | Dataset SHA | Commit |
|:---|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|
| `bm25_skills` | **0.4017** | 0.6806 | **0.5680** | **0.5404** | 511 | `bm25` | `b731a25c` | `7f1868e` |
| `oracle` | **0.5564** | 0.6806 | **1.0000** | **0.8520** | 511 | `bm25` | `b731a25c` | `7f1868e` |
| `random` | **0.1349** | 0.6806 | **0.3850** | **0.2454** | 511 | `none` | `b731a25c` | `7f1868e` |
| `v0_naive` | **0.2867** | 0.6806 | **0.7417** | **0.4617** | 511 | `bge-small-en-v1.5` | `b731a25c` | `7f1868e` |
| `v0_naive_unfiltered` | **0.0519** | 0.6806 | **0.1904** | **0.0845** | 511 | `bge-small-en-v1.5` | `b731a25c` | `7f1868e` |

---

### Performance by Freelancer Persona

| Variant | Persona | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `bm25_skills` | AI/ML (Dr. Elena Rostova) | 182 | 0.4346 | 0.7404 | 0.7376 | 0.5897 |
| `bm25_skills` | Full-Stack Web (Marcus Vance) | 172 | 0.3331 | 0.6680 | 0.4302 | 0.4689 |
| `bm25_skills` | Data Analysis (Amina Al-Mansoor) | 157 | 0.4387 | 0.6250 | 0.5223 | 0.5615 |
| `oracle` | AI/ML (Dr. Elena Rostova) | 182 | 0.6122 | 0.7404 | 1.0000 | 0.8508 |
| `oracle` | Full-Stack Web (Marcus Vance) | 172 | 0.4966 | 0.6680 | 1.0000 | 0.8191 |
| `oracle` | Data Analysis (Amina Al-Mansoor) | 157 | 0.5573 | 0.6250 | 1.0000 | 0.8895 |
| `random` | AI/ML (Dr. Elena Rostova) | 182 | 0.1335 | 0.7404 | 0.3675 | 0.2388 |
| `random` | Full-Stack Web (Marcus Vance) | 172 | 0.1287 | 0.6680 | 0.3617 | 0.2381 |
| `random` | Data Analysis (Amina Al-Mansoor) | 157 | 0.1433 | 0.6250 | 0.4307 | 0.2612 |
| `v0_naive` | AI/ML (Dr. Elena Rostova) | 182 | 0.2911 | 0.7404 | 0.8188 | 0.4993 |
| `v0_naive` | Full-Stack Web (Marcus Vance) | 172 | 0.2953 | 0.6680 | 0.7162 | 0.4550 |
| `v0_naive` | Data Analysis (Amina Al-Mansoor) | 157 | 0.2723 | 0.6250 | 0.6801 | 0.4253 |
| `v0_naive_unfiltered` | AI/ML (Dr. Elena Rostova) | 182 | 0.0840 | 0.7404 | 0.2155 | 0.1043 |
| `v0_naive_unfiltered` | Full-Stack Web (Marcus Vance) | 172 | 0.0245 | 0.6680 | 0.0853 | 0.0468 |
| `v0_naive_unfiltered` | Data Analysis (Amina Al-Mansoor) | 157 | 0.0446 | 0.6250 | 0.2765 | 0.1029 |

---

### Performance by Requirement Complexity (`n_requirements`)

| Variant | Requirements | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `bm25_skills` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `bm25_skills` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `bm25_skills` | 5+ skills | 511 | 0.4017 | 0.6806 | 0.5680 | 0.5404 |
| `oracle` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `oracle` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `oracle` | 5+ skills | 511 | 0.5564 | 0.6806 | 1.0000 | 0.8520 |
| `random` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `random` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `random` | 5+ skills | 511 | 0.1349 | 0.6806 | 0.3850 | 0.2454 |
| `v0_naive` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 5+ skills | 511 | 0.2867 | 0.6806 | 0.7417 | 0.4617 |
| `v0_naive_unfiltered` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive_unfiltered` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive_unfiltered` | 5+ skills | 511 | 0.0519 | 0.6806 | 0.1904 | 0.0845 |
