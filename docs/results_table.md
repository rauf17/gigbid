# GigBid Evaluation Results Table

This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Decompose, V2 Hybrid BM25+Dense, V3 Cross-Encoder Rerank, V4 Outcome-Aware), agent decision nodes, proposal verification (R5), and adversarial prompt injection defense (R9).

> [!NOTE]
> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).
> Metrics are automatically updated by running `make eval-all`, `make eval-nodes`, or `uv run python scripts/results_table.py`.

---

### Overall Retrieval Performance

| Variant | Mode | Recall@5 | R@5 Ceiling | MRR | nDCG@10 | p95 Lat (ms) | Tokens | USD | Queries | Embedder | Dataset SHA | Commit |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|
| `random` | `deterministic` | **0.1349** | 0.6806 | **0.3850** | **0.2454** | 0.0 | 0 | $0.0000 | 511 | `none` | `b731a25c` | `7f1868e` |
| `bm25_text` | `deterministic` | **0.2760** | 0.6806 | **0.6229** | **0.4720** | 20.4 | 0 | $0.0000 | 511 | `none` | `b731a25c` | `d6e46c2` |
| `skill_tag_lookup_REFERENCE`* | `deterministic` | **0.4017** | 0.6806 | **0.5680** | **0.5404** | 2.1 | 0 | $0.0000 | 511 | `none` | `b731a25c` | `d6e46c2` |
| `v0_naive` | `deterministic` | **0.2867** | 0.6806 | **0.7417** | **0.4617** | 88.9 | 0 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `7d8f600` |
| `v1_decompose` | `real` | **0.2276** | 0.6806 | **0.6660** | **0.4014** | 1671.9 | 363,928 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `7d8f600` |
| `v2_hybrid` | `deterministic` | **0.3121** | 0.6806 | **0.7363** | **0.4870** | 296.7 | 0 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `d6e46c2` |
| `v3_rerank` | `deterministic` | **0.3308** | 0.6806 | **0.7397** | **0.4878** | 2982.4 | 0 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `7d8f600` |
| `v4_outcome` | `deterministic` | **0.3298** | 0.6806 | **0.7396** | **0.4880** | 133.2 | 0 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `7d8f600` |
| `oracle` | `deterministic` | **0.5564** | 0.6806 | **1.0000** | **0.8520** | 0.0 | 0 | $0.0000 | 511 | `bm25` | `b731a25c` | `7f1868e` |
| `v0_naive_unfiltered` | `deterministic` | **0.0519** | 0.6806 | **0.1904** | **0.0845** | 0.0 | 0 | $0.0000 | 511 | `bge-small-en-v1.5` | `b731a25c` | `7f1868e` |

> [!NOTE]
> `* skill_tag_lookup_REFERENCE`: queries the skills field the gold labels were derived from; leaks the answer key; reference only (excluded from ranking and ablation).

---

### Performance by Freelancer Persona

| Variant | Persona | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `random` | AI/ML (Dr. Elena Rostova) | 182 | 0.1335 | 0.7404 | 0.3675 | 0.2388 |
| `random` | Full-Stack Web (Marcus Vance) | 172 | 0.1287 | 0.6680 | 0.3617 | 0.2381 |
| `random` | Data Analysis (Amina Al-Mansoor) | 157 | 0.1433 | 0.6250 | 0.4307 | 0.2612 |
| `bm25_text` | AI/ML (Dr. Elena Rostova) | 182 | 0.2988 | 0.7404 | 0.7081 | 0.5311 |
| `bm25_text` | Full-Stack Web (Marcus Vance) | 172 | 0.2145 | 0.6680 | 0.4993 | 0.3885 |
| `bm25_text` | Data Analysis (Amina Al-Mansoor) | 157 | 0.3169 | 0.6250 | 0.6594 | 0.4949 |
| `skill_tag_lookup_REFERENCE` | AI/ML (Dr. Elena Rostova) | 182 | 0.4346 | 0.7404 | 0.7376 | 0.5897 |
| `skill_tag_lookup_REFERENCE` | Full-Stack Web (Marcus Vance) | 172 | 0.3331 | 0.6680 | 0.4302 | 0.4689 |
| `skill_tag_lookup_REFERENCE` | Data Analysis (Amina Al-Mansoor) | 157 | 0.4387 | 0.6250 | 0.5223 | 0.5615 |
| `v0_naive` | AI/ML (Dr. Elena Rostova) | 182 | 0.2911 | 0.7404 | 0.8188 | 0.4993 |
| `v0_naive` | Full-Stack Web (Marcus Vance) | 172 | 0.2953 | 0.6680 | 0.7162 | 0.4550 |
| `v0_naive` | Data Analysis (Amina Al-Mansoor) | 157 | 0.2723 | 0.6250 | 0.6801 | 0.4253 |
| `v1_decompose` | AI/ML (Dr. Elena Rostova) | 182 | 0.2094 | 0.7404 | 0.6585 | 0.3788 |
| `v1_decompose` | Full-Stack Web (Marcus Vance) | 172 | 0.2277 | 0.6680 | 0.6904 | 0.4003 |
| `v1_decompose` | Data Analysis (Amina Al-Mansoor) | 157 | 0.2484 | 0.6250 | 0.6481 | 0.4288 |
| `v2_hybrid` | AI/ML (Dr. Elena Rostova) | 182 | 0.3450 | 0.7404 | 0.8319 | 0.5546 |
| `v2_hybrid` | Full-Stack Web (Marcus Vance) | 172 | 0.2787 | 0.6680 | 0.7141 | 0.4407 |
| `v2_hybrid` | Data Analysis (Amina Al-Mansoor) | 157 | 0.3105 | 0.6250 | 0.6497 | 0.4595 |
| `v3_rerank` | AI/ML (Dr. Elena Rostova) | 182 | 0.4322 | 0.7404 | 0.7393 | 0.5170 |
| `v3_rerank` | Full-Stack Web (Marcus Vance) | 172 | 0.2499 | 0.6680 | 0.6362 | 0.4332 |
| `v3_rerank` | Data Analysis (Amina Al-Mansoor) | 157 | 0.3018 | 0.6250 | 0.8535 | 0.5137 |
| `v4_outcome` | AI/ML (Dr. Elena Rostova) | 182 | 0.4295 | 0.7404 | 0.7391 | 0.5252 |
| `v4_outcome` | Full-Stack Web (Marcus Vance) | 172 | 0.2499 | 0.6680 | 0.6353 | 0.4277 |
| `v4_outcome` | Data Analysis (Amina Al-Mansoor) | 157 | 0.3018 | 0.6250 | 0.8546 | 0.5109 |
| `oracle` | AI/ML (Dr. Elena Rostova) | 182 | 0.6122 | 0.7404 | 1.0000 | 0.8508 |
| `oracle` | Full-Stack Web (Marcus Vance) | 172 | 0.4966 | 0.6680 | 1.0000 | 0.8191 |
| `oracle` | Data Analysis (Amina Al-Mansoor) | 157 | 0.5573 | 0.6250 | 1.0000 | 0.8895 |
| `v0_naive_unfiltered` | AI/ML (Dr. Elena Rostova) | 182 | 0.0840 | 0.7404 | 0.2155 | 0.1043 |
| `v0_naive_unfiltered` | Full-Stack Web (Marcus Vance) | 172 | 0.0245 | 0.6680 | 0.0853 | 0.0468 |
| `v0_naive_unfiltered` | Data Analysis (Amina Al-Mansoor) | 157 | 0.0446 | 0.6250 | 0.2765 | 0.1029 |

---

### Performance by Requirement Complexity (`n_requirements`)

| Variant | Requirements | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `random` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `random` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `random` | 5+ skills | 511 | 0.1349 | 0.6806 | 0.3850 | 0.2454 |
| `bm25_text` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `bm25_text` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `bm25_text` | 5+ skills | 511 | 0.2760 | 0.6806 | 0.6229 | 0.4720 |
| `skill_tag_lookup_REFERENCE` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `skill_tag_lookup_REFERENCE` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `skill_tag_lookup_REFERENCE` | 5+ skills | 511 | 0.4017 | 0.6806 | 0.5680 | 0.5404 |
| `v0_naive` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive` | 5+ skills | 511 | 0.2867 | 0.6806 | 0.7417 | 0.4617 |
| `v1_decompose` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v1_decompose` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v1_decompose` | 5+ skills | 511 | 0.2276 | 0.6806 | 0.6660 | 0.4014 |
| `v2_hybrid` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v2_hybrid` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v2_hybrid` | 5+ skills | 511 | 0.3121 | 0.6806 | 0.7363 | 0.4870 |
| `v3_rerank` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v3_rerank` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v3_rerank` | 5+ skills | 511 | 0.3308 | 0.6806 | 0.7397 | 0.4878 |
| `v4_outcome` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v4_outcome` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v4_outcome` | 5+ skills | 511 | 0.3298 | 0.6806 | 0.7396 | 0.4880 |
| `oracle` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `oracle` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `oracle` | 5+ skills | 511 | 0.5564 | 0.6806 | 1.0000 | 0.8520 |
| `v0_naive_unfiltered` | 1-2 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive_unfiltered` | 3-4 skills | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `v0_naive_unfiltered` | 5+ skills | 511 | 0.0519 | 0.6806 | 0.1904 | 0.0845 |

---

### Agent Benchmarks Summary

| Benchmark | Mode | Primary Metric | Primary Value | p95 Lat (ms) | Real LLM Calls | Models Used |
|:---|:---:|:---|:---:|:---:|:---|:---|
| Decision Pipeline | `real` | Bid/Skip F1 | **0.7500** | 921.85 | `0` | `analyst:openai/gpt-oss-20b, risk_assessor:openai/gpt-oss-20b, fit_matcher:openai/gpt-oss-20b, pricing:deterministic_heuristics, decision:pure_function` |
| Proposal Verification (R5) | `real` | Post-Verify Unsupported Rate | **0.0000** | 1411.7 | `0` | `analyst:openai/gpt-oss-20b, fit_matcher:openai/gpt-oss-20b, writer:openai/gpt-oss-120b, verifier:openai/gpt-oss-120b, critic:openai/gpt-oss-120b, compliance:deterministic_heuristics` |
| Injection Defense (R9) | `real` | Defense Effectiveness Rate | **0.7778** | 2722.5 | `0` | `risk_assessor:openai/gpt-oss-20b` |

---

### Agent Decision Pipeline Performance

| Metric | Value |
|:---|:---:|
| **LLM Mode** | **`real`** |
| Jobs Evaluated | 78 |
| **Bid/Skip F1 Score** | **0.7500** |
| Bid/Skip Precision | 0.6000 |
| Bid/Skip Recall | 1.0000 |
| Bid/Skip Accuracy | 0.6923 |
| Scam Detection Precision | 1.0000 |
| Scam Detection Recall | 0.2778 |
| **Injection Detection Rate** | **1.0000** |
| Price-in-Band Rate | 0.8846 |
| Latency p95 (ms) | 921.85 |
| Total Tokens | 0 |
| Total Cost (USD) | $0.0000 |
| Non-Cache LLM Calls | `0` |
| Models Used | `analyst:openai/gpt-oss-20b, risk_assessor:openai/gpt-oss-20b, fit_matcher:openai/gpt-oss-20b, pricing:deterministic_heuristics, decision:pure_function` |
| Dataset SHA / Commit | `b731a25c` / `94b1696` |

---

### Proposal Claim Verification & Quality (R5)

| Metric | Value |
|:---|:---:|
| **LLM Mode** | **`real`** |
| Proposals Evaluated | 15 |
| Avg Claims per Proposal | 1.00 |
| Unsupported Claims Before Verification | 0 |
| Unsupported Claims After Verification | 0 |
| Unsupported Rate Before Verification | 0.0000 |
| **Unsupported Rate After Verification** | **0.0000** |
| **Unsupported Rate Reduction (R5 Delta)** | **0.0000** |
| Critic Grounding Score (Mean) | 0.8500 |
| Critic Personalization Score (Mean) | 0.8000 |
| Critic Accept Rate | 0.0000 |
| Compliance Clean Rate | 1.0000 |
| Total Compliance Violations Caught | 0 |
| Latency p95 (ms) | 1411.7 |
| Non-Cache LLM Calls | `0` |
| Models Used | `analyst:openai/gpt-oss-20b, fit_matcher:openai/gpt-oss-20b, writer:openai/gpt-oss-120b, verifier:openai/gpt-oss-120b, critic:openai/gpt-oss-120b, compliance:deterministic_heuristics` |
| Dataset SHA / Commit | `b731a25c` / `d42e2ba` |

---

### Adversarial Prompt Injection Defense (R9)

| Metric | Value |
|:---|:---:|
| **LLM Mode** | **`real`** |
| Total Adversarial Jobs Tested | 10 |
| **Attack Success Rate (Without Defenses)** | **0.9000** |
| **Attack Success Rate (With Defenses)** | **0.2000** |
| **ASR Absolute Reduction** | **0.7000** |
| **Defense Effectiveness Rate** | **0.7778** |
| Injection Flagging Rate | 0.8000 |
| Latency p95 (ms) | 2722.5 |
| Non-Cache LLM Calls | `0` |
| Models Used | `risk_assessor:openai/gpt-oss-20b` |
| Dataset SHA / Commit | `b731a25c` / `d42e2ba` |
