# GigBid Data Card

This document describes the datasets used across GigBid, including data provenance, synthesis methods, schemas, and known limitations.

---

## 1. Synthetic Persona Data

### 1.1 Overview & Motivation
Because the original course persona corpora were not centrally distributed, GigBid generates deterministic, reproducible synthetic persona profiles. All synthetic records are explicitly tagged with `"synthetic": true` to maintain transparent data lineage and avoid confusing mock data with live marketplace interactions.

Three distinct professional personas are generated:
1. **`ai_ml` (Dr. Elena Rostova)**: Senior AI/ML Systems Engineer & LLM Specialist focusing on RAG, vector retrieval, MLOps, and model evaluation.
2. **`fullstack` (Marcus Vance)**: Full-Stack Web & Cloud Systems Architect focusing on Next.js/React frontends, FastAPI/Node APIs, Stripe subscription billing, and real-time WebSockets.
3. **`data_analyst` (Amina Al-Mansoor)**: Lead Data Analyst & Analytics Engineering Specialist focusing on SQL, dbt data models, Snowflake/BigQuery data warehouses, executive BI dashboards, and cohort churn analytics.

### 1.2 Generation Method
The dataset is generated deterministically via `data/scripts/gen_personas.py` using seeded pseudo-randomness (`seed=42`).
- **Zero LLM Dependency**: No external or paid LLM API calls are required to generate or verify this data.
- **Fast Execution**: Full generation across all 3 personas completes in under 2 seconds.
- **Reproducibility**: Running `python data/scripts/gen_personas.py --seed 42` guarantees bitwise reproducible JSON, JSONL, and Markdown outputs.

### 1.3 Persona Corpus Layout
For each persona ID (`data/personas/<persona_id>/`):
- `profile.json`: Contains structured freelancer metadata, rates (hourly, floor rate, minimum fixed-price project size), weekly Connects budget, search filters (min client rating, min client spend, disallowed keywords), technical skills, and background summary.
- `cv.md`: Full Markdown CV detailing education, certifications, core proficiencies, and enterprise project histories.
- `cv.pdf`: Rendered multi-page PDF document generated via standard-compliant PDF writer, verifiable with `pypdf`.
- `case_studies/*.md`: 20 detailed Markdown case studies per persona with YAML front-matter (`id`, `project`, `skills`, `date`, `client_industry`, `outcome`, `synthetic: true`).
- `repos/<name>/`: 2 realistic code repositories per persona (serving as stand-ins for GitHub portfolio ingestion). Each contains a `README.md` and 2–4 clean, typed code files (`.py`, `.ts`, `.tsx`, or `.sql`) with `synthetic: true` headers.
- `reviews.json`: 12 verified client reviews detailing client names, industries, project titles, numerical ratings (4.8–5.0), project spend, and feedback.
- `past_proposals.jsonl`: 150 historical proposals per persona categorized by job title, proposal text, outcome, and submission date.

### 1.4 Proposal Quality & Outcome Correlation Rule
The proposal dataset adheres strictly to the following quality correlation rule:
> **Won proposals must cite a specific project and metric from that persona’s case studies, replied proposals cite skills but no metrics, and ignored proposals are generic openers.**

- **Won Proposals (`won`)**:
  - High quality and evidence-grounded.
  - Cites a specific project name (or one of its stylistic aliases) and the exact quantitative outcome metric from the persona's case studies (e.g., *"Sub-second retrieval latency on 4.5M pages with 91% factual accuracy"*).
  - Plausibly correlates with human hiring preferences on freelance marketplaces.
- **Replied Proposals (`replied`)**:
  - Medium quality.
  - Cites relevant technical skills and architectural approaches, but provides **no** specific quantitative project metrics.
- **Ignored Proposals (`ignored`)**:
  - Low quality.
  - Generic openers without project specifics, quantitative metrics, or differentiated technical arguments (e.g., *"Hello! I am very interested in your job posting... Please hire me..."*).

### 1.5 Messiness & Realism Simulation
Real freelance portfolios and bid histories are rarely uniform. The generator introduces structural messiness:
1. **Multiple Project Aliases**: The same case study is cited across proposals using three different styles:
   - *Formal title*: e.g., "Enterprise RAG Document Intelligence System"
   - *Colloquial description*: e.g., "the 4.5M page semantic legal search engine I shipped in Q1"
   - *Architectural component*: e.g., "our vector retrieval backend and chunking pipeline"
2. **Implicit Skills**: Concepts and techniques are described without naming brand keywords (e.g., *"benchmarked cosine vs inner product distances over high-dimensional float32 tensors with HNSW index tuning"* rather than simply writing "pgvector").
3. **Code Mixed with Prose**: Technical proposals feature inline code snippets (`Python`, `TypeScript`, `SQL`) interleaved directly into the proposal copy.

### 1.6 Limitations
- **Simulated Client Feedback**: Reviews and ratings are synthetically generated and do not reflect unpredictable human client dynamics or negative edge cases (ratings cluster between 4.8 and 5.0).
- **Synthetic Codebases**: Repositories provide small, realistic samples (2–4 files each) suitable for RAG chunking and tool demonstrations, rather than full production monorepos.
- **Static Job Distribution**: Historical proposal job titles are drawn from a curated template distribution rather than live Upwork scraping.
- **Pricing Uniformity**: Rates adhere to persona-level floor and target rates rather than complex dynamic negotiations.

---

## 2. Job Stream Data

### 2.1 Provenance & Synthesis
`data/raw/` was empty, so the jobs are synthetic. No Kaggle data or CC0 licence was used for the generated dataset.

If Kaggle files are placed in data/raw/, prepare_jobs.py uses them; record the licence from the dataset page.

All job records are deterministically generated by `data/scripts/prepare_jobs.py` (seed=42) using **coherent job archetypes**. Each archetype defines a synchronized title, description template, and a coherent skill set together, ensuring that job descriptions explicitly reference 3–6 of their required skills in prose rather than sampling skills independently of the job text. External raw files placed in `data/raw/` are gitignored to avoid committing unverified third-party data.

### 2.2 Target Schema
Every job record in `jobs_historical.jsonl` and `jobs_stream.jsonl` conforms to:
- `id` (`str`): Unique identifier (e.g. `job_hist_00001`, `job_stream_00001`).
- `title` (`str`): Cleaned job post title.
- `description` (`str`): Detailed project description and client requirements.
- `category` (`str`): Mapped to one of the three target domains: `"AI/ML"`, `"Full-Stack Web"`, or `"Data Analysis"`.
- `skills` (`list[str]`): List of required or preferred technical skill tags.
- `budget_type` (`str`): `"fixed"` or `"hourly"`.
- `budget_min` (`float`): Minimum budget (USD or hourly rate).
- `budget_max` (`float`): Maximum budget (USD or hourly rate).
- `client_country` (`str`): Country of origin for the hiring client.
- `posted_at` (`str`): ISO 8601 UTC timestamp.
- `connects_cost` (`int`): Realistic Connects fee (4, 8, 12, or 16) calculated from budget tiers.
- `synthetic` (`bool`): `true` for all jobs in this synthetic corpus.

### 2.3 Datasets Produced
1. **`data/processed/jobs_historical.jsonl` (1,500 jobs)**:
   - Historical job corpus used for calculating market clearing price distributions, typical budget bands, and category rate baselines.
   - Evenly partitioned across the three categories (500 AI/ML, 500 Full-Stack Web, 500 Data Analysis).
   - Spans historical post timestamps over a 180-day window.
2. **`data/processed/jobs_stream.jsonl` (600 jobs)**:
   - Released as the active simulation stream served by the student-built GigSim server.
   - Contains 492 clean jobs and 108 planted adversarial instances.

### 2.4 Adversarial Instances & Hidden Labels
`data/scripts/inject_adversarial.py` plants adversarial patterns into the `jobs_stream.jsonl` pool only:
- **Duplicates (~5%, 30 jobs)**: Near-identical reposts of existing clean jobs with slightly modified titles, identical requirements, and delayed timestamps (`is_duplicate_of: <original_job_id>`).
- **Scams (~8%, 48 jobs)**:
  - *`free_work`* (12 jobs): Requests for unpaid functional prototypes or finished code before contract award.
  - *`unpaid_test`* (12 jobs): Mandatory multi-day or 10-hour unpaid assessment tasks.
  - *`off_platform_contact`* (12 jobs): Direct communication requests to bypass platform escrow (e.g. Telegram `@global_talent_99`, WhatsApp).
  - *`crypto_payment`* (12 jobs): Demands to settle invoices strictly in USDT/Bitcoin outside platform escrow.
- **Prompt Injections (~5%, 30 jobs)**:
  - *`direct_override`* (8 jobs): Top-level instructions ordering the agent to ignore previous instructions and force bid approval.
  - *`hidden_middle`* (8 jobs): Injections disguised inside technical requirement paragraphs.
  - *`delimiter_confusion`* (7 jobs): Fake Markdown/JSON role boundaries simulating end-of-user input.
  - *`xml_tag`* (7 jobs): Faux `<system_override>` and `<agent_policy_override>` tags.

**Hidden Labels (`data/processed/jobs_gold_labels.jsonl`)**:
- Contains 600 records mapping each stream job ID to its ground truth label:
  `{"id": str, "is_duplicate_of": str|null, "is_scam": bool, "scam_type": str|null, "has_injection": bool, "injection_style": str|null}`
- **Security Rule**: These labels are reserved strictly for offline evaluation runners (`evals/runners/decision_eval.py`) and are **never exposed** by the GigSim REST API.

### 2.5 Synthetic Fields
- Since `data/raw/` was empty, all fields across `jobs_historical.jsonl`, `jobs_stream.jsonl`, and `jobs_gold_labels.jsonl` are 100% synthetically generated.

### 2.6 Limitations
- The simulated stream uses a fixed template vocabulary for technical requirements.
- Prompt injection patterns are representative of known prompt injection benchmarks but do not cover adaptive multi-turn jailbreaks.
- Client budget distributions follow standard tier approximations rather than long-tail macroeconomic fluctuations.

---

## 3. Dev Evaluation Set

### 3.1 Overview & Motivation
In accordance with AI-4016 Assignment B4, the instructor's dev evaluation set was never distributed, so GigBid synthesizes an offline development evaluation set labeled `SYNTHETIC`. All records are deterministically generated by `data/scripts/build_dev_set.py` (`seed=42`) with zero external LLM dependencies.

### 3.2 Dataset Composition & Sampling
Dev sets are stored under `evals/datasets/`:
- `evals/datasets/dev_ai_ml.jsonl`: 200 jobs for Dr. Elena Rostova (`ai_ml`).
- `evals/datasets/dev_fullstack.jsonl`: 200 jobs for Marcus Vance (`fullstack`).
- `evals/datasets/dev_data_analyst.jsonl`: 200 jobs for Amina Al-Mansoor (`data_analyst`).

Each 200-job set is sampled deterministically from the combined 2,100 job pool (1,500 historical + 600 stream jobs):
- **150 in-category jobs**: Matching the persona's core category (AI/ML, Full-Stack Web, or Data Analysis).
- **50 out-of-category jobs (~25%)**: Sampled from the other two categories to ensure negative examples and verify that the decision engine learns to skip non-matching categories.

### 3.3 Gold Label Specification & Decision Rules
Thresholds and parameters are governed by `evals/datasets/gold_rules.yaml`. Each line in `dev_<persona>.jsonl` contains `job` and `gold`:
1. **`bid_or_skip` (`str` in `{"bid", "skip"}`)**:
   - `skip` if `is_scam == true`.
   - `skip` if `job.category != persona.primary_category`.
   - `skip` if skill overlap ratio $|job\_skills \cap persona\_skills| / |job\_skills| < 0.35$.
   - `skip` if budget falls below persona floor rate:
     - `ai_ml`: hourly $< \$60/\text{hr}$, fixed $< \$1,000$.
     - `fullstack`: hourly $< \$50/\text{hr}$, fixed $< \$800$.
     - `data_analyst`: hourly $< \$45/\text{hr}$, fixed $< \$600$.
   - Else `bid`.
2. **`is_scam` (`bool`) & `has_injection` (`bool`)**:
   - Mapped from `data/processed/jobs_gold_labels.jsonl` (historical jobs default to `false`).
3. **`relevant_evidence_ids` (`list[str]`)**:
   - Ground-truth item-level evidence IDs selected from the persona's experience portfolio: case studies (`{persona}_cs_<id>`), code repositories (`{persona}_repo_<name>`), and verified client reviews (`{persona}_review_<id>`).
   - Ground-truth items exclude past proposals (which represent historical bid outcome signals rather than direct experience evidence) and CV chunks (which are broad profile overviews).
   - Filter rule: Jaccard similarity between job skills and item skills $\ge 0.20$, prioritizing case studies, code repositories, then client reviews. Bounded to a maximum of 8 evidence items.
   - **No Minimum-1 Fallback**: The artificial 'minimum 1 gold item' fallback has been removed. Jobs that the freelancer persona should skip (out-of-category jobs or jobs lacking genuine skill overlap) legitimately have empty gold evidence (`[]`).
   - Jobs with empty gold evidence are excluded from retrieval evaluation metrics (Recall@5, MRR, nDCG@10) but remain fully active for downstream decision evaluation.
   - During evaluation, fine-grained retrieval chunks (e.g. repo source code chunks or README sections) are rolled up to their corresponding item/project IDs (deduplicating while preserving best rank) so evaluation operates at the unified item level.
4. **`fair_price_band` (`list[float]`)**:
   - `[p25, p75]` percentiles of comparable jobs from `jobs_historical.jsonl` sharing category, budget type, and skill overlap.
5. **`n_requirements` (`int`)**:
   - Number of distinct skill requirements specified in the job post, used for eval slicing (`1-2`, `3-4`, `5+`).

### 3.4 Tool Calling Benchmark (`evals/datasets/tool_tasks.jsonl`)
Contains 40 evaluation tasks covering all three MCP servers:
- **`marketplace` (16 tasks)**: Job search, job details, client history, Connects balance, draft creation, proposal submission, messaging.
- **`portfolio` (14 tasks)**: Semantic evidence retrieval, case study retrieval, technical skill listing.
- **`workspace` (10 tasks)**: Calendar slot inspection, tentative holds, email draft generation.

Schema per record:
```json
{
  "task_id": "task_01",
  "prompt": "Search active job listings in the AI/ML category matching vector search requirements.",
  "persona": "ai_ml",
  "server": "marketplace",
  "expected_tool": "search_jobs",
  "expected_args_subset": {"category": "AI/ML", "query": "vector search"}
}
```

### 3.5 Circularity Limitation
> [!WARNING]
> **Circularity Limitation of Ground-Truth Evidence Labels**:
> The gold retrieval relevance labels (`relevant_evidence_ids`) are synthesized via structured skill set overlap (Jaccard similarity between job skill tags and chunk skill tags). RAG retrieval pipelines (V0 dense semantic, V1 hybrid BM25 + dense, V2 multi-representation) ingest the unstructured text of the job description to retrieve chunk texts.
>
> Because the ground truth was generated from skill overlap, retrieval algorithms that align closely with explicit skill keyword matching inherently achieve higher recall and nDCG scores on this dev set. This benchmark does not penalize models that fail to capture nuanced latent domain knowledge not expressed in the explicit skill taxonomy.

---

## 4. Ethical Considerations & Data Provenance
- All persona names ("Dr. Elena Rostova", "Marcus Vance", "Amina Al-Mansoor") and client names are entirely fictitious.
- No real-world Personally Identifiable Information (PII), proprietary client code, or live Upwork user tokens are present in this repository.
- Compliance with the university assignment rules is maintained by keeping all synthetic generation deterministic, auditable, and isolated from live marketplace credentials.
