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

### Hypothesis Testing
- **Reply Rate**:
  - $z$-statistic: $2.5726$
  - Two-sided $p$-value: **$0.0101$** ($p < 0.05$)
  - **Verdict**: Statistically significant. We reject the null hypothesis of equal reply rates.
- **Hire Rate**:
  - $z$-statistic: $2.2597$
  - Two-sided $p$-value: **$0.0238$** ($p < 0.05$)
  - **Verdict**: Statistically significant. Arm A yields significantly higher direct hires than Arm B.

---

## 4. Sub-Group Analysis by Persona

| Persona | Arm A Reply Rate | Arm B Reply Rate | Difference | $z$-statistic | $p$-value | Significant ($\alpha=0.05$)? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `ai_ml` | 7.50% (3/40) | 2.50% (1/40) | +5.00% | 1.0260 | 0.3049 | No (underpowered at $n=40$) |
| `data_analyst` | 25.00% (10/40) | 12.50% (5/40) | +12.50% | 1.4322 | 0.1521 | No (underpowered at $n=40$) |
| `fullstack` | 37.50% (15/40) | 17.50% (7/40) | **+20.00%** | 2.0031 | **0.0452** | **Yes** ($p < 0.05$) |

---

## 5. Discussion & Interpretation

1. **Why Result-First Wins**: Clients scanning tens of proposals prioritize instant risk reduction. An opener citing a concrete benchmark with evidence tag (`[E:id]`) immediately satisfies specificity and metric affinity filters, whereas questions place cognitive burden on the client before credibility is established.
2. **Persona Variance**: Fullstack clients exhibit the strongest sensitivity to quantifiable openers ($+20.0\%$, $p = 0.0452$), likely because web/API deliverables have clear latency and throughput metrics. For `ai_ml` and `data_analyst`, Arm A remains directionally superior, though larger sample sizes ($n \ge 100$ per persona) would be required to establish standalone per-persona significance.
