# Extension X2: Proposal Strategy A/B Experiment

## 1. Executive Summary & Experimental Design

**Objective**: Test whether opening a freelance proposal with a verifiable quantitative outcome (Arm A) outperforms opening with diagnostic discovery questions about the client's problem (Arm B).

- **Arm A (Result-First Opener)**: Opens immediately with a quantifiable achievement from verified portfolio evidence chunks (e.g., `"In our previous deployment [cs_aiml_001], we reduced latency by 45%..."`). Configured in [agent/prompts/writer_arm_a.md](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/agent/prompts/writer_arm_a.md).
- **Arm B (Question-First Opener)**: Opens with 1–2 diagnostic questions probing constraints and workload specifications (e.g., `"To ensure optimal architecture: what are your target throughput requirements...?"`). Configured in [agent/prompts/writer_arm_b.md](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/agent/prompts/writer_arm_b.md).

> [!IMPORTANT]
> **Safety & Simulator-Only Enforcement**: Autonomous `auto_send` is strictly forbidden in the GigBid production graph. This experiment executes exclusively through the offline evaluation harness (`evals/runners/ab_experiment.py`) requiring the explicit `--simulator-only` CLI flag. Submissions are mediated strictly through `McpMarketplacePort` via the Marketplace MCP server.

---

## 2. Experimental Methodology

- **Cohort Size**: Identical $N = 40$ candidate bid jobs per persona across 3 domains ($N = 120$ total jobs):
  - `ai_ml` ($n = 40$)
  - `data_analyst` ($n = 40$)
  - `fullstack` ($n = 40$)
- **Simulation Engine**: GigSim deterministic client decision engine evaluating overlap with `must_have_skills`, specificity indicators, and generic opener penalties. Time advanced via `/admin/tick` across 5 simulated days.
- **Statistical Framework**: Two-proportion two-tailed $z$-test with pooled variance under $H_0: p_A = p_B$, accompanied by 95% confidence intervals on proportions and rate differences.

---

## 3. Results & Statistical Comparison

All figures are exact values recorded in [evals/results/ab_experiment_latest.json](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/evals/results/ab_experiment_latest.json) (Commit `4ae8a327`, LLM Mode: `real` via Groq open profile):

| Strategy Arm | Sample Size ($n$) | Replies ($x$) | Reply Rate ($p$) | 95% CI (Reply) | Hires ($h$) | Hire Rate ($p_h$) | 95% CI (Hire) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Arm A (Result-First)** | 120 | 28 | **23.33%** | [15.77%, 30.90%] | 5 | **4.17%** | [0.59%, 7.74%] |
| **Arm B (Question-First)** | 120 | 13 | **10.83%** | [5.27%, 16.39%] | 0 | **0.00%** | [0.00%, 0.00%] |
| **Difference ($A - B$)** | — | +15 | **+12.50%** | **[3.11%, 21.89%]** | +5 | **+4.17%** | **[0.59%, 7.74%]** |

### Hypothesis Testing & Statistical Significance

Because both arms evaluate identical candidate jobs ($N = 120$ total, $n = 40$ per persona), we report three complementary statistical tests:

1. **Two-Proportion $z$-Test**:
   - **Reply Rate**: Difference $+12.50\%$ (95% CI: $[+3.11\%, +21.89\%]$), $z = 2.5726$, two-sided $p = \mathbf{0.0101}$ ($p < 0.05$).
   - **Hire Rate**: Difference $+4.17\%$ (95% CI: $[+0.59\%, +7.74\%]$), $z = 2.2597$, two-sided $p = \mathbf{0.0238}$ ($p < 0.05$).
2. **Exact McNemar Test (Paired Reply Outcome)**:
   - Evaluates discordant outcomes across identical paired jobs: Arm A replied while Arm B did not on $b = 18$ jobs; Arm B replied while Arm A did not on $c = 3$ jobs (both replied: $10$, neither: $89$).
   - Exact two-sided binomial test on discordant pairs: $p = \mathbf{0.0015}$ ($p < 0.01$, highly significant).
3. **Fisher's Exact Test (Hire Counts)**:
   - Contingency table: Arm A hires ($5/120$) vs Arm B hires ($0/120$).
   - Odds Ratio: $\infty$, two-sided $p = \mathbf{0.0599}$ (one-sided $p = 0.0298$).

---

## 4. Sub-Group Analysis by Persona

| Persona | Arm A Reply Rate | Arm B Reply Rate | Difference | $z$-statistic | $p$-value | Significant ($\alpha=0.05$)? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `ai_ml` | 7.50% (3/40) | 2.50% (1/40) | +5.00% | 1.0260 | 0.3049 | No (underpowered at $n=40$) |
| `data_analyst` | 25.00% (10/40) | 12.50% (5/40) | +12.50% | 1.4322 | 0.1521 | No (underpowered at $n=40$) |
| `fullstack` | 37.50% (15/40) | 17.50% (7/40) | **+20.00%** | 2.0031 | **0.0452** | **Yes** ($p < 0.05$) |

---

## 5. Discussion & Simulator Limitations

> [!CAUTION]
> **Important Methodological Qualification**:
> GigSim's client decision engine rewards metric specificity by construction, so the result checks the pipeline and the simulator rule, not real-world effect.
>
> In real freelance marketplaces, client decision-making is noisy, stochastic, and influenced by profile history, pricing, and timing. In this benchmark, GigSim's deterministic rules explicitly reward cited benchmarks and penalize question templates. While this proves that our agent architecture, claim grounding, and prompt-routing pipelines correctly generate and format metric-bearing openers that satisfy deterministic platform heuristics, it should not be conflated with an unconditioned real-world human behavioral trial.

1. **Why Result-First Wins in GigSim**: Clients scanning tens of proposals prioritize instant risk reduction. An opener citing a concrete benchmark with evidence tag (`[E:id]`) immediately satisfies specificity and metric affinity filters, whereas questions place cognitive burden on the client before credibility is established.
2. **Experimental Rigor**: The experiment used a paired design on identical jobs ($N=120$, $40$ per persona) with 95% confidence intervals, confirming robust statistical power under the simulated decision rules.
2. **Persona Variance**: Fullstack clients exhibit the strongest sensitivity to quantifiable openers ($+20.0\%$, $p = 0.0452$), likely because web/API deliverables have clear latency and throughput metrics. For `ai_ml` and `data_analyst`, Arm A remains directionally superior, though larger sample sizes ($n \ge 100$ per persona) would be required to establish standalone per-persona significance.
