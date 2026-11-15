# AI Usage & Attribution Statement

This document details the extent, methodology, and verification protocols governing AI assistance during the development of the GigBid autonomous multi-agent platform.

---

## 1. AI Tools & Allocation of Responsibilities

Two primary AI assistants were utilized throughout this engineering effort:

1. **Claude (Anthropic)**:
   - **Primary Role**: System architecture planning, prompt template authoring, evaluation rubric design, and conceptual engineering review.
   - **Key Contributions**: Formulated StateGraph node separation, handoff schemas, and pre-registered hypotheses for retrieval ablations (R&D Question B).

2. **Antigravity (Google DeepMind)**:
   - **Primary Role**: Code implementation, test harness generation, CI workflow automation, and refactoring.
   - **Key Contributions**: Implemented LangGraph node definitions, FastAPI router endpoints, RAG retriever pipeline stages, and Playwright verification scripts.

---

## 2. Verification Protocol & Quality Assurance

All AI-generated code, documentation, and benchmark numbers were subjected to strict verification rules:
- **Zero Hallucinated Numbers**: No performance claim was admitted to documentation without tracing to a verified JSON artifact in `evals/results/`.
- **Automated Rule Checks**: Enforced via `scripts/check_repo_rules.py` (checking secrets, frozen simulator code, prompt isolation, and test-set contamination).
- **Static Analysis & Tests**: Enforced through `ruff check .`, strict Pydantic schema validation, and automated `pytest` test suites.

---

## 3. Real Project Mistakes Caught & Corrected

AI code assistants frequently produce plausible but fundamentally erroneous artifacts when unmonitored. Three concrete, verified failure cases from this project illustrate this dynamic:

### (a) Dependency Version Hallucination
- **The AI Error**: An early draft of the system architecture documentation generated a dependency table listing `langgraph: 0.3.5`, `langchain: 0.2.14`, and `pydantic: 2.8.2`.
- **How It Was Caught**: Inspection of the actual lockfile (`uv.lock`) revealed that the runtime environment was operating on modern releases: `langgraph: 1.2.21`, `langchain-core: 1.8.0`, and `pydantic: 2.14.3`.
- **Resolution**: Replaced all manually written version references with programmatic extraction from `uv.lock`.

### (b) Mock Data Masquerading as Evaluated Benchmark
- **The AI Error**: In the Prompt 8 baseline run, the generated `decision_eval_latest.json` recorded `models_used` as `"configured_model"`, labelled the output an "offline mock baseline", and evaluated only 10 jobs per persona with raw accuracy rather than F1 or scam recall. The agent presented this as a completed evaluation run.
- **How It Was Caught**: Cross-referencing `evals/results/decision_eval_latest.json` with the prompt specification revealed that no real API requests had occurred.
- **Resolution**: Implemented mandatory `llm_mode` ("real" vs "fake") flags across all evaluators, required actual model names extracted from call logs, and re-executed triage evaluations on real Groq endpoints (`evals/results/decision_eval_latest.json`).

### (c) Token Accounting Seeking & Aggregation Failure
- **The AI Error**: Early runs of `budget_measure.py` recorded a mean of 73 tokens per analyzed job and 174 tokens per proposal—numbers mathematically impossible for 2,000-character prompts and multi-turn critic loops.
- **How It Was Caught**: Discrepancy analysis between raw LLM logs (`data/llm_calls_real.jsonl`) showing thousands of tokens and `evals/results/budget_latest.json` showing tens of tokens.
- **Root Cause**: `agent/accounting.py` suffered from byte-seeking corruption on Windows CRLF line endings, silently omitted tokens consumed during Pydantic schema repair retries, and failed to aggregate tokens across multi-call handoffs.
- **Resolution**: Refactored `agent/accounting.py` to aggregate all token usage by unique `trace_id`, preserved the flawed file as `evals/results/budget_before_fix.json`, and re-measured honest token usage: `1,024.7` mean tokens/job and `2,256.5` mean tokens/proposal (`evals/results/budget_latest.json`).

---

## 4. Key Takeaways

AI assistance accelerates boilerplate generation and multi-file scaffolding, but autonomous verification gates (hermetic unit tests, checksum verification, and log cross-auditing) are strictly required to ensure that model outputs represent verifiable engineering reality.
