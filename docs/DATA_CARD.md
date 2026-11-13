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

## 2. Ethical Considerations & Data Provenance
- All persona names ("Dr. Elena Rostova", "Marcus Vance", "Amina Al-Mansoor") and client names are entirely fictitious.
- No real-world Personally Identifiable Information (PII), proprietary client code, or live Upwork user tokens are present in this repository.
- Compliance with the university assignment rules is maintained by keeping all synthetic generation deterministic, auditable, and isolated from live marketplace credentials.
