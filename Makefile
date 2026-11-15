.PHONY: install dev api test eval eval-smoke eval-all eval-nodes eval-nodes-smoke seed data demo lint check lock mcp-marketplace mcp-portfolio mcp-workspace ingest db-up db-down
db-up:
	docker compose -f infra/docker-compose.yml up -d postgres redis
	uv run python scripts/migrate_db.py
db-down:
	docker compose -f infra/docker-compose.yml down
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
mcp-workspace:
	uv run uvicorn mcp_servers.workspace.server:app --port 8003 --reload
ingest:
	uv run python -m rag.ingest --persona all
api:
	uv run uvicorn apps.api.main:app --reload --port 8000
worker:
	uv run arq worker.main.WorkerSettings
openapi:
	uv run python scripts/export_openapi.py
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
eval-nodes-smoke:
	uv run python evals/runners/decision_eval.py --smoke
	uv run python evals/runners/proposal_eval.py --smoke
	uv run python evals/runners/injection_eval.py --smoke
	uv run python scripts/results_table.py
eval-nodes:
	uv run python evals/runners/decision_eval.py
	uv run python evals/runners/proposal_eval.py
	uv run python evals/runners/injection_eval.py
	uv run python scripts/results_table.py
demo:
	@echo "TODO: run one job inbox -> approval -> reply against GigSim (Phase 4)"
