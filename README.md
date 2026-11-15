# GigBid: a multi-agent freelancer copilot

> TODO (Phase 7): 30-second demo GIF here.

**Live:** TODO · **Demo video:** TODO · **Portfolio MCP:** TODO · **Write-up:** TODO

## What it does
LangGraph agents find freelance jobs, judge whether to bid, draft proposals grounded in portfolio
evidence, and manage client conversations. A human approves every proposal and message.

## Architecture
TODO (diagram from docs/ARCHITECTURE.md)

## Results
Every number below is traced to an artifact in `evals/results/` and indexed in [docs/results_index.md](docs/results_index.md):

- **RAG Retrieval (Hybrid V2 vs Baseline V0)**: Recall@5 improved from `0.2867` to `0.3121` (+2.54 pts; AI/ML domain: `0.3450`), nDCG@10 reached `0.4870`.
- **Decision Engine (Triage)**: Bid/Skip F1: `0.7500`, Recall: `1.0000`, Precision: `0.6000`, Price-in-band: `0.8846`.
- **Proposal Generation & Claim Verification**: Hallucinations reduced from `0.1953` (19.53%) down to `0.0000` (0.00%) unsupported claims; Compliance clean rate: `1.0000`.
- **Security & Prompt Injection**: Delimiter defenses reduced Attack Success Rate (ASR) from `0.9000` to `0.2000` (70.0% reduction, `0.7778` defense effectiveness).
- **Proposal Strategy A/B Experiment (Extension X2)**: Result-first opener (Arm A) achieved `0.2333` reply rate and `0.0417` hire rate vs question-first opener (Arm B) with `0.1083` reply rate and `0.0000` hire rate (reply delta `+0.1250`, $p = 0.0101$; hire delta `+0.0417`, $p = 0.0238$, both statistically significant).

## Run locally
```bash
cp .env.example .env
make install
make dev        # docker compose up
```

Pinned dependency versions: see `uv.lock`.
