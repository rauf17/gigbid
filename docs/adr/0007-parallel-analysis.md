# ADR 0007: Parallel Analysis Fan-Out (Analyst, Risk Assessor, Fit Matcher) via LangGraph Send

**Status:** accepted

## Context
In the GigBid autonomous bidding pipeline, assessing a new job opportunity requires three evaluations:
1. Technical requirement decomposition (`analyst`)
2. Safety, scam, and injection screening (`risk_assessor`)
3. Portfolio capability alignment and evidence retrieval (`fit_matcher`)

Two control-flow architectures were evaluated:
- **Option A: Sequential Pipeline (`analyst` $\to$ `risk_assessor` $\to$ `fit_matcher`)**:
  The Analyst runs first, generating a structured `JobSpec`. The Risk Assessor and Fit Matcher sequentially consume `JobSpec`.
- **Option B: Parallel Fan-Out via `Send` (`intake` $\to$ [`analyst`, `risk_assessor`, `fit_matcher`] in parallel $\to$ `join`)**:
  The three assessment nodes execute concurrently upon job intake.

## Decision
We select **Option B: Parallel Fan-Out via LangGraph `Send`**.

### Trade-Off Analysis: Duplicate Extraction Cost vs. End-to-End Latency
1. **Latency Reduction**:
   In Option A, sequential execution incurs cumulative LLM latency:
   $$T_{\text{sequential}} = T_{\text{analyst}} (\sim 1.2\text{s}) + T_{\text{risk}} (\sim 0.9\text{s}) + T_{\text{fit}} (\sim 1.1\text{s}) \approx 3.2\text{s}$$
   Under Option B, parallel execution reduces latency to the maximum duration of the slowest branch:
   $$T_{\text{parallel}} = \max(T_{\text{analyst}}, T_{\text{risk}}, T_{\text{fit}}) \approx 1.2\text{s}$$
   This achieves a $\sim 62\%$ reduction in assessment latency, critical for competitive bidding on fast-moving job streams.
2. **Decoupling Fit Matcher from Analyst**:
   To enable parallel execution, `fit_matcher` does not wait for `JobSpec`. It extracts atomic search tokens directly from `job["skills"]` and cached requirement templates (`rag.stages.decompose`).
3. **Resource Cost**:
   If a job is flagged as an obvious scam by `risk_assessor`, running `fit_matcher` in parallel expends embedding and retrieval computations on a job that will ultimately be skipped. However, because portfolio retrieval operates over local BM25 and Qdrant vector indices, the dollar cost is negligible ($\approx \$0.00$), while the user-visible latency benefit is substantial.

## Consequences
- `intake` issues parallel `Send` calls to `analyst`, `risk_assessor`, and `fit_matcher`.
- A dedicated `join` node aggregates state updates before routing to `decide`.
- State fields (`spec`, `risk`, `fit`) are independent disjoint fields in `BidGraphState`.
