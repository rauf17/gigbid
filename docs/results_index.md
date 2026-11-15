# Results Index: Verified Metrics & Artifact Map

This index maps every quantitative claim and benchmark cited in the project report and documentation directly to its underlying JSON artifact in `evals/results/` and its verified git commit.

---

## 1. Retrieval Pipeline & RAG Ablations (R&D Question B)

Source dataset: 600 synthetic jobs in `evals/datasets/dev_<persona>.jsonl`. Commit: `4ae8a327`.

| Metric / Variant | Value | File Source | Commit | Description |
| :--- | :---: | :--- | :--- | :--- |
| **V0 Naive Dense Recall@5** | `0.2867` | [rag_v0_naive_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v0_naive_latest.json) | `4ae8a327` | Baseline dense embedding retrieval over chunked portfolio |
| **V0 Naive Dense MRR** | `0.7417` | [rag_v0_naive_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v0_naive_latest.json) | `4ae8a327` | Mean Reciprocal Rank for V0 baseline |
| **V0 Naive Dense nDCG@10** | `0.4617` | [rag_v0_naive_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v0_naive_latest.json) | `4ae8a327` | Normalized Discounted Cumulative Gain at rank 10 |
| **V0 Naive Dense p95 Latency** | `88.93` | [rag_v0_naive_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v0_naive_latest.json) | `4ae8a327` | 95th percentile latency in milliseconds |
| **V1 Decompose Recall@5** | `0.2276` | [rag_v1_decompose_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v1_decompose_latest.json) | `4ae8a327` | Multi-query decomposition per extracted requirement |
| **V1 Decompose MRR** | `0.6660` | [rag_v1_decompose_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v1_decompose_latest.json) | `4ae8a327` | Mean Reciprocal Rank for decomposition stage |
| **V1 Decompose nDCG@10** | `0.4014` | [rag_v1_decompose_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v1_decompose_latest.json) | `4ae8a327` | nDCG@10 for decomposition pipeline |
| **V1 Decompose p95 Latency** | `1671.93` | [rag_v1_decompose_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v1_decompose_latest.json) | `4ae8a327` | 95th percentile latency in milliseconds |
| **V2 Hybrid Recall@5** | `0.3121` | [rag_v2_hybrid_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v2_hybrid_latest.json) | `4ae8a327` | Reciprocal Rank Fusion of BM25 text and dense vector |
| **V2 Hybrid MRR** | `0.7363` | [rag_v2_hybrid_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v2_hybrid_latest.json) | `4ae8a327` | Mean Reciprocal Rank for hybrid RRF |
| **V2 Hybrid nDCG@10** | `0.4870` | [rag_v2_hybrid_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v2_hybrid_latest.json) | `4ae8a327` | nDCG@10 for hybrid lexical-semantic pipeline |
| **V2 Hybrid p95 Latency** | `296.68` | [rag_v2_hybrid_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v2_hybrid_latest.json) | `4ae8a327` | 95th percentile latency in milliseconds |
| **V3 Cross-Encoder Recall@5** | `0.3308` | [rag_v3_rerank_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v3_rerank_latest.json) | `4ae8a327` | Cross-encoder reranked top-30 candidates |
| **V3 Cross-Encoder MRR** | `0.7397` | [rag_v3_rerank_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v3_rerank_latest.json) | `4ae8a327` | Mean Reciprocal Rank after cross-encoder scoring |
| **V3 Cross-Encoder nDCG@10** | `0.4878` | [rag_v3_rerank_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v3_rerank_latest.json) | `4ae8a327` | nDCG@10 after transformer reranking |
| **V3 Cross-Encoder p95 Latency**| `2982.38`| [rag_v3_rerank_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v3_rerank_latest.json) | `4ae8a327` | Highest latency cost stage (transformer cross-encoder) |
| **V4 Outcome Boost Recall@5** | `0.3298` | [rag_v4_outcome_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v4_outcome_latest.json) | `4ae8a327` | Win-rate boosted evidence retrieval |
| **V4 Outcome Boost MRR** | `0.7396` | [rag_v4_outcome_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v4_outcome_latest.json) | `4ae8a327` | Mean Reciprocal Rank with outcome weighting |
| **V4 Outcome Boost nDCG@10** | `0.4880` | [rag_v4_outcome_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v4_outcome_latest.json) | `4ae8a327` | nDCG@10 with outcome weighting |
| **V4 Outcome Boost p95 Latency**| `133.16` | [rag_v4_outcome_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_v4_outcome_latest.json) | `4ae8a327` | 95th percentile latency in milliseconds |
| **BM25 Lexical Recall@5** | `0.2760` | [rag_bm25_text_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_bm25_text_latest.json) | `4ae8a327` | Pure BM25 text retrieval baseline |
| **Skill Tag Lookup Recall@5** | `0.4017` | [rag_skill_tag_lookup_REFERENCE_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_skill_tag_lookup_REFERENCE_latest.json) | `4ae8a327` | Reference exact skill metadata lookup |
| **Random Baseline Recall@5** | `0.1349` | [rag_random_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_random_latest.json) | `4ae8a327` | Random sampling baseline |
| **Oracle Baseline Recall@5** | `0.5564` | [rag_oracle_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/rag_oracle_latest.json) | `4ae8a327` | Gold ground-truth upper-bound retrieval |

---

## 2. Pre-Registered Hypotheses (R&D Question B)

Documented in [docs/rd/hypotheses.md](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/docs/rd/hypotheses.md).

| Hypothesis | Claimed Metric | Measured Metric | Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **H1 (V2 Hybrid)** | Recall@5 $\ge +0.08$ | V0 `0.2867` $\rightarrow$ V2 `0.3121` | `+0.0254` (+2.54 pts; AI/ML persona: `0.2222` $\rightarrow$ `0.3450`, `+0.1228` / +12.28 pts) | **Refuted** (overall) |
| **H2 (V3 Rerank)** | Costliest stage p95 latency | V2 `296.68ms` $\rightarrow$ V3 `2982.38ms` | `+2685.70ms` | **Confirmed** (latency) |
| **H3 (V1 Decompose)** | Hurts overall; high LLM cost | V0 `0.2867` $\rightarrow$ V1 `0.2276`, `363928` tokens consumed | `-0.0591` (-5.91 pts) | **Confirmed** |
| **H4 (V4 Outcome)** | Neutral effect on gold Recall@5 | V3 `0.3308` $\rightarrow$ V4 `0.3298` | `-0.0010` (-0.10 pts) | **Confirmed** |

---

## 3. Decision Evaluation & Triage Performance

Source: [evals/results/decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) (Mode: `real`, Commit: `4ae8a327`).

| Metric | Value | File Source | Description |
| :--- | :---: | :--- | :--- |
| **Evaluated Jobs** | `78` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Total evaluated development set opportunities |
| **Bid/Skip F1 Score** | `0.7500` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Macro harmonic mean of precision and recall |
| **Bid/Skip Recall** | `1.0000` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | 100% recall on genuine profitable opportunities |
| **Bid/Skip Precision** | `0.6000` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Precision on bidding recommendations |
| **Bid/Skip Accuracy** | `0.6923` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Overall classification accuracy |
| **Total Scam Jobs** | `18` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Placed scam/off-platform diversion opportunities |
| **Scam Precision** | `1.0000` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Zero false-positive scam accusations |
| **Scam Recall** | `0.2778` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | 5 / 18 scam leads detected by deterministic heuristics |
| **Price In-Band Rate** | `0.8846` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | 88.46% of submitted bid prices fell inside client budget bands |
| **Decision Latency p50** | `310.64` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | Median triage decision latency in milliseconds |
| **Decision Latency p95** | `921.85` | [decision_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/decision_eval_latest.json) | 95th percentile triage decision latency in milliseconds |

---

## 4. Proposal Evaluation & Claim Verification

Source: [evals/results/proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) (Mode: `real`, Commit: `4ae8a327`).

| Metric | Value | File Source | Description |
| :--- | :---: | :--- | :--- |
| **Proposals Evaluated** | `15` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | End-to-end verified generated proposals |
| **Average Claims / Letter** | `20.33` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | Mean atomic factual claims extracted per proposal |
| **Unsupported Rate (Before)** | `0.1953` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | 19.53% ungrounded claims generated by writer draft |
| **Unsupported Rate (After)** | `0.0000` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | 0.00% unsupported claims post-verifier redaction |
| **Hallucination Reduction** | `0.1953` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | Full eradication of ungrounded factual assertions |
| **Critic Personalization** | `0.8500` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | Mean personalization rating from LLM critique |
| **Compliance Clean Rate** | `1.0000` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | 100% of final proposals clean of contact/payment violations |
| **Proposal Latency p50** | `32173.75` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | Median proposal generation latency in milliseconds |
| **Proposal Latency p95** | `69939.54` | [proposal_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/proposal_eval_latest.json) | 95th percentile proposal generation latency in milliseconds |

---

## 5. Security & Prompt Injection Defense

Source: [evals/results/injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) (Mode: `real`, Commit: `4ae8a327`).

| Metric | Value | File Source | Description |
| :--- | :---: | :--- | :--- |
| **Adversarial Test Rows** | `10` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | Planted prompt injections across dev sets |
| **ASR (Without Defenses)** | `0.9000` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | 90.0% attack success rate on raw prompt concatenation |
| **ASR (With Defenses)** | `0.2000` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | 20.0% residual attack success rate with delimiters |
| **ASR Reduction** | `0.7000` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | 70.0% absolute reduction in exploit vulnerability |
| **Defense Effectiveness** | `0.7778` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | 77.78% relative risk mitigation |
| **Injection Detection Rate** | `0.8000` | [injection_eval_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/injection_eval_latest.json) | 80.0% of adversarial payloads actively detected |

---

## 6. Proposal Strategy A/B Experiment (Extension X2)

Source: [evals/results/ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) (Mode: `real`, Commit: `4ae8a327`).

| Metric | Value | File Source | Description |
| :--- | :---: | :--- | :--- |
| **Evaluated Cohort ($N$)** | `120` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | 40 candidate jobs per persona across 3 domains |
| **Arm A Reply Rate** | `0.2333` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | 23.33% (28/120) reply rate for result-first opener |
| **Arm B Reply Rate** | `0.1083` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | 10.83% (13/120) reply rate for question-first opener |
| **Reply Rate Difference** | `+0.1250` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | +12.50 percentage points advantage for Arm A |
| **Reply $z$-statistic** | `2.5726` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | Two-proportion $z$-statistic |
| **Reply $p$-value** | `0.0101` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | Statistically significant ($p < 0.05$) |
| **Arm A Hire Rate** | `0.0417` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | 4.17% (5/120) hire rate for result-first opener |
| **Arm B Hire Rate** | `0.0000` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | 0.00% (0/120) hire rate for question-first opener |
| **Hire Rate Difference** | `+0.0417` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | +4.17 percentage points advantage for Arm A |
| **Hire $z$-statistic** | `2.2597` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | Two-proportion $z$-statistic |
| **Hire $p$-value** | `0.0238` | [ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) | Statistically significant ($p < 0.05$) |

---

## 7. Declared Budget & End-to-End Latency/Cost Accounting

Source: [evals/results/budget_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/budget_latest.json) (Mode: `real`, Commit: `4ae8a327`, `LLM_CACHE=0`).

| Phase / Target | Declared Target | Measured Value | Unit | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Job Analysed Latency (p50)** | — | `19.747` | seconds | Measured baseline |
| **Job Analysed Latency (p95)** | `12.0` | `20.487` | seconds | Rate-limit retries elevated tail |
| **Job Analysed Mean Cost** | `0.01` | `0.000000` | USD | Well within budget (Groq free tier) |
| **Proposal Latency (p50)** | — | `22.723` | seconds | Measured baseline |
| **Proposal Latency (p95)** | `25.0` | `61.126` | seconds | Rate-limit retries elevated tail |
| **Proposal Mean Cost** | `0.03` | `0.000000` | USD | Well within budget (Groq free tier) |
