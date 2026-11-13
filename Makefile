.PHONY: install dev api test eval seed demo lint check lock
install:
	uv sync --extra dev
lock:
	uv lock
dev:
	docker compose -f infra/docker-compose.yml up --build
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
eval:
	@echo "TODO: retrieval + decision + GigSim outcome evals -> evals/results/*.json (Phase 5)"
demo:
	@echo "TODO: run one job inbox -> approval -> reply against GigSim (Phase 4)"
