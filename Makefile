.PHONY: install dev api test eval eval-smoke eval-all seed data demo lint check lock mcp-marketplace mcp-portfolio ingest
install:
	uv sync --extra dev
lock:
	uv lock
dev:
	# Starts local infrastructure (Postgres, Redis) or run services individually:
	# make api (port 8000), make mcp-marketplace (port 8002), make seed (port 8081)
	docker compose -f infra/docker-compose.yml up --build
mcp-marketplace:
	uv run uvicorn mcp_servers.marketplace.server:app --port 8002 --reload
mcp-portfolio:
	uv run uvicorn mcp_servers.portfolio.server:app --port 8001 --reload
ingest:
	uv run python -m rag.ingest --persona all
api:
	uv run uvicorn apps.api.main:app --reload --port 8000
test:
	uv run pytest -q
lint:
	uv run ruff check . && uv run python scripts/check_repo_rules.py
check:
	uv run python scripts/check_repo_rules.py
seed:
	uv run python gigsim/seed.py
data:
	uv run python data/scripts/gen_personas.py
	uv run python data/scripts/prepare_jobs.py
	uv run python data/scripts/inject_adversarial.py
	uv run python gigsim/seed.py
eval:
	uv run python -m evals.runners.rag_eval --variant v0_naive
	uv run python scripts/results_table.py
eval-smoke:
	uv run python -m evals.runners.rag_eval --smoke
eval-all:
	uv run python -m evals.runners.rag_eval --variant random
	uv run python -m evals.runners.rag_eval --variant bm25_text
	uv run python -m evals.runners.rag_eval --variant skill_tag_lookup_REFERENCE
	uv run python -m evals.runners.rag_eval --variant v0_naive
	uv run python -m evals.runners.rag_eval --variant v1_decompose
	uv run python -m evals.runners.rag_eval --variant v2_hybrid
	uv run python -m evals.runners.rag_eval --variant v3_rerank
	uv run python -m evals.runners.rag_eval --variant v4_outcome
	uv run python scripts/results_table.py
demo:
	@echo "TODO: run one job inbox -> approval -> reply against GigSim (Phase 4)"
