# GigBid: a multi-agent freelancer copilot

> TODO (Phase 7): 30-second demo GIF here.

**Live:** TODO · **Demo video:** TODO · **Portfolio MCP:** TODO · **Write-up:** TODO

## What it does
LangGraph agents find freelance jobs, judge whether to bid, draft proposals grounded in portfolio
evidence, and manage client conversations. A human approves every proposal and message.

## Architecture
TODO (diagram from docs/ARCHITECTURE.md)

## Results
Every number below must trace to a file in `evals/results/`.
TODO

## Run locally
```bash
cp .env.example .env
make install
make dev        # docker compose up
```

Pinned dependency versions: see `uv.lock`.
