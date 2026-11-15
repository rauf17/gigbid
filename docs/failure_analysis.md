# Failure Analysis & Root Cause Investigation (Report Section 8)

This document provides a systematic analysis of real failure cases encountered across benchmark runs in `evals/results/`.

Every case below is documented and verified from actual result artifacts (`evals/results/ablation_latest.json`). Per project audit rules, only failures with traceable individual job records in result files are listed in the case breakdown; taxonomy classes with aggregate-only metrics or zero recorded failures are explicitly itemized.

---

## Failure Taxonomy

The platform defines 8 taxonomy classes:
1. **Missed Evidence**: Retrieval failed to locate relevant portfolio chunks or ranked irrelevant chunks above gold evidence.
2. **Wrong Skip**: Decision node skipped a viable, high-margin, high-fit job.
3. **Mispriced**: Quoted bid price fell outside client willingness-to-pay or breached freelancer floor rate.
4. **Unsupported Claim**: Proposal writer hallucinated metrics, deliverables, or experience not substantiated by evidence chunks.
5. **Generic Opening**: Proposal utilized banned, template-like, or spammy opening greetings penalized by client decision engines.
6. **Compliance Miss**: Proposal contained off-platform contact, external links, guarantees, or policy infractions.
7. **Injection**: Adversarial jailbreak or instruction override in untrusted job posting manipulated downstream agent actions.
8. **Tool Error**: MCP or database communication failure, schema mismatch, or rate-limit exhaustion.

---

## Recorded Real Failure Cases (Traced to `evals/results/ablation_latest.json`)

All 5 traced per-job failures occurred under the **Missed Evidence** taxonomy class during the RAG pipeline ablation experiment on persona `fullstack`.

### Case 1: Entity Down-Ranking by Cross-Encoder / Hybrid Fusion
- **Job ID**: `job_hist_00943`
- **Persona**: `fullstack`
- **Taxonomy Class**: Missed Evidence
- **Source Artifact**: `evals/results/ablation_latest.json` (traced: `failure_cases[0]`)
- **What Happened**: Cross-encoder reranker / hybrid BM25 sparse fusion dropped nDCG@10 from 0.6049 (V0 Naive) to 0.0000 and Recall@5 from 0.3333 to 0.0000 on "Senior LLM Engineer for Production RAG Pipeline", missing gold chunk `fullstack_cs_cs_fs_010`.
- **Root Cause**: BM25 keyword fusion and cross-encoder relevance scoring over-weighted generic resume matches (`fullstack_cv`) and pushed exact technical entity matches (`saas-subscription-core`, `rev_fullstack_010`) out of top-5.
- **Fix Tried**: V4 outcome-aware heuristic reranking adding review rating weighting and technical token preservation.
- **Aggregate effect of related change (not a per-job rerun)**: Domain nDCG@10 improved from 0.4993 (V0) to 0.5252 (V4) (`evals/results/ablation_latest.json`).

---

### Case 2: Sparse-Dense Keyword Dilution in Hybrid Fusion
- **Job ID**: `job_stream_00031`
- **Persona**: `fullstack`
- **Taxonomy Class**: Missed Evidence
- **Source Artifact**: `evals/results/ablation_latest.json` (traced: `failure_cases[1]`)
- **What Happened**: Reciprocal Rank Fusion (RRF) scored nDCG@10 = 0.0000 (Recall@5 = 0.0000 vs 0.3333 in V0), missing all 3 gold evidence chunks.
- **Root Cause**: BM25 vocabulary mismatch on hyphenated skill tags (`pgvector`, `LangChain`) diluted sparse scores, allowing general web development chunks to rank higher.
- **Fix Tried**: Query decomposition (V1) to issue atomic sub-queries per skill requirement.
- **Aggregate effect of related change (not a per-job rerun)**: V1 decomposition dropped Recall@5 to 0.2276 (underperforming baseline V0 = 0.2867); V2 Hybrid achieved Recall@5 = 0.3121 across the 511-query dev corpus (`evals/results/ablation_latest.json`).

---

### Case 3: Inadequate Repository Chunk Semantic Density
- **Job ID**: `job_stream_00340`
- **Persona**: `fullstack`
- **Taxonomy Class**: Missed Evidence
- **Source Artifact**: `evals/results/ablation_latest.json` (traced: `failure_cases[2]`)
- **What Happened**: Top-5 retrieval missed gold repository chunk `fullstack_repo_saas-subscription-core` (nDCG@10 drop = 0.6049).
- **Root Cause**: Repository summaries lacked rich contextual narratives compared to full case studies, resulting in lower dense cosine similarity.
- **Fix Tried**: Ingestion enrichment prepending repository README descriptions and architecture bullet points.
- **Aggregate effect of related change (not a per-job rerun)**: V3 reranker overall Recall@5 rose from 0.2867 to 0.3308 (`evals/results/ablation_latest.json`).

---

### Case 4: Review Chunk Truncation and Low Head Confidence
- **Job ID**: `job_stream_00454`
- **Persona**: `fullstack`
- **Taxonomy Class**: Missed Evidence
- **Source Artifact**: `evals/results/ablation_latest.json` (traced: `failure_cases[3]`)
- **What Happened**: Gold testimonial `fullstack_review_rev_fullstack_010` was demoted out of top-5 (nDCG@10 drop = 0.6049).
- **Root Cause**: Testimonials are short text snippets (30–60 tokens), causing cross-encoders trained on long passage pairs to assign lower raw logits.
- **Fix Tried**: V4 outcome heuristic multiplier adding a +0.15 score boost for 5-star client reviews.
- **Aggregate effect of related change (not a per-job rerun)**: V4 maintained overall nDCG@10 = 0.4880 across all 511 dev queries (`evals/results/ablation_latest.json`).

---

### Case 5: Distractor Proximity Without Strict Entity Matching
- **Job ID**: `job_stream_00472`
- **Persona**: `fullstack`
- **Taxonomy Class**: Missed Evidence
- **Source Artifact**: `evals/results/ablation_latest.json` (traced: `failure_cases[4]`)
- **What Happened**: Dense retriever retrieved distractor case studies (`fullstack_cs_cs_fs_015`, `019`, `020`) ahead of gold evidence `fullstack_cs_cs_fs_010`.
- **Root Cause**: Vector space proximity across technical terms pulled general fullstack case studies with high generic term overlap instead of the specific RAG case study.
- **Fix Tried**: Mandatory persona-scoped metadata filtering combined with exact entity boost.
- **Aggregate effect of related change (not a per-job rerun)**: Filtered baseline achieved Recall@5 = 0.2867 (nDCG@10 = 0.4617) vs unfiltered Recall@5 = 0.0519 (nDCG@10 = 0.0845) (`evals/results/ablation_latest.json`).

---

## Taxonomy Classes & Aggregate Failure Traceability Audit

The assignment specification targets $\ge 10$ real failed jobs. However, official benchmark result files (`evals/results/*.json`) contain exactly 5 failure entries with traceable individual job IDs (the 5 cases above from `evals/results/ablation_latest.json`). The remaining classes break down as follows:

1. **Injection (Real Failures, Aggregate Record Only)**: `evals/results/injection_eval_latest.json` records that with defenses active, 2 of 10 adversarial attacks succeeded (Attack Success Rate with Defenses = 0.2000; 1 in `ai_ml`, 1 in `data_analyst`). These 2 adversarial penetrations are real platform failures, but the eval runner recorded only aggregate metrics without preserving individual job IDs.
2. **Wrong Skip & False Bids (Real Failures, Aggregate Record Only)**: `evals/results/decision_eval_latest.json` achieved Bid/Skip precision of 0.6000 across 78 evaluation jobs (meaning 40.0% of bids were false positives placed on non-viable jobs), and scam recall was 0.2778 (missing 13 of 18 scam postings). These represent real decision failures, but the runner emitted only aggregate counts rather than per-job failure ID lists.
3. **Unsupported Claim**: Zero failures recorded in `evals/results/proposal_eval_latest.json` (post-verification unsupported claim rate = 0.0000; two-stage claim verifier eliminated 100% of detected hallucinations).
4. **Generic Opening**: Zero failures recorded in `evals/results/proposal_eval_latest.json` (compliance clean rate = 1.0000; no generic epistolary openings passed the critic loop).
5. **Compliance Miss**: Zero failures recorded in `evals/results/proposal_eval_latest.json` (100.0% clean compliance rate; 0 policy infractions across all evaluated proposals).
6. **Mispriced**: Aggregate price-in-band rate achieved 0.8846 in `evals/results/decision_eval_latest.json` (88.5% within client willingness-to-pay), but no per-job failure IDs were emitted.
7. **Tool Error**: Zero failures recorded across benchmark runs (0 MCP tool exceptions or database errors).

**Summary**: Rather than fabricating synthetic job identifiers to reach the 10-job threshold, exactly 5 traceable per-job failures are reported from the result artifacts, alongside the aggregate counts of injection penetrations (2) and decision false bids.
