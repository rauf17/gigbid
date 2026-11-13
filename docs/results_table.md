# GigBid Evaluation Results Table

This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Hybrid BM25+Dense, V2 Multi-Representation) and downstream decision runners.

> [!NOTE]
> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).
> Metrics are automatically updated by running `make eval` or `uv run python scripts/results_table.py`.

---

### Overall Retrieval Performance

| Variant | Recall@5 | MRR | nDCG@10 | Queries | Embedder | Dataset SHA | Commit |
|:---|:---:|:---:|:---:|:---:|:---|:---:|:---:|
| `bm25_skills` | **0.0964** | **0.1647** | **0.1386** | 600 | `bm25` | `ac7d46be` | `f2ccb94` |
| `oracle` | **0.7085** | **1.0000** | **0.8925** | 600 | `bm25` | `ac7d46be` | `f2ccb94` |
| `random` | **0.1619** | **0.3086** | **0.2243** | 600 | `none` | `ac7d46be` | `f2ccb94` |
| `v0_naive` | **0.0563** | **0.1234** | **0.0603** | 600 | `bge-small-en-v1.5` | `ac7d46be` | `f2ccb94` |

---

### Performance by Freelancer Persona

| Variant | Persona | Queries | Recall@5 | MRR | nDCG@10 |
|:---|:---|:---:|:---:|:---:|:---:|
| `bm25_skills` | AI/ML (Dr. Elena Rostova) | 200 | 0.1597 | 0.2748 | 0.2148 |
| `bm25_skills` | Full-Stack Web (Marcus Vance) | 200 | 0.0839 | 0.1290 | 0.1101 |
| `bm25_skills` | Data Analysis (Amina Al-Mansoor) | 200 | 0.0458 | 0.0902 | 0.0910 |
| `oracle` | AI/ML (Dr. Elena Rostova) | 200 | 0.7503 | 1.0000 | 0.9205 |
| `oracle` | Full-Stack Web (Marcus Vance) | 200 | 0.7096 | 1.0000 | 0.8890 |
| `oracle` | Data Analysis (Amina Al-Mansoor) | 200 | 0.6656 | 1.0000 | 0.8679 |
| `random` | AI/ML (Dr. Elena Rostova) | 200 | 0.1831 | 0.3109 | 0.2305 |
| `random` | Full-Stack Web (Marcus Vance) | 200 | 0.1648 | 0.3030 | 0.2277 |
| `random` | Data Analysis (Amina Al-Mansoor) | 200 | 0.1378 | 0.3119 | 0.2148 |
| `v0_naive` | AI/ML (Dr. Elena Rostova) | 200 | 0.0256 | 0.0308 | 0.0234 |
| `v0_naive` | Full-Stack Web (Marcus Vance) | 200 | 0.1050 | 0.0977 | 0.0875 |
| `v0_naive` | Data Analysis (Amina Al-Mansoor) | 200 | 0.0383 | 0.2417 | 0.0699 |

---

### Performance by Requirement Complexity (`n_requirements`)

| Variant | Requirements | Queries | Recall@5 | MRR | nDCG@10 |
|:---|:---:|:---:|:---:|:---:|:---:|
| `bm25_skills` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 |
| `bm25_skills` | 3-4 skills | 408 | 0.1019 | 0.1623 | 0.1427 |
| `bm25_skills` | 5+ skills | 192 | 0.0849 | 0.1696 | 0.1299 |
| `oracle` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 |
| `oracle` | 3-4 skills | 408 | 0.7651 | 1.0000 | 0.9123 |
| `oracle` | 5+ skills | 192 | 0.5882 | 1.0000 | 0.8504 |
| `random` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 |
| `random` | 3-4 skills | 408 | 0.1544 | 0.2721 | 0.2118 |
| `random` | 5+ skills | 192 | 0.1778 | 0.3864 | 0.2509 |
| `v0_naive` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 3-4 skills | 408 | 0.0546 | 0.1056 | 0.0561 |
| `v0_naive` | 5+ skills | 192 | 0.0599 | 0.1612 | 0.0691 |
