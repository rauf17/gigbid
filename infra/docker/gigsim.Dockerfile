# GigSim Marketplace Simulator Service
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml README.md ./
RUN uv pip install --system --no-cache fastapi uvicorn[standard] pyyaml httpx pydantic

COPY gigsim/ ./gigsim/
COPY data/ ./data/

EXPOSE 8081

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD curl -f http://localhost:8081/health || exit 1

CMD ["sh", "-c", "python gigsim/seed.py && uvicorn gigsim.app:app --host 0.0.0.0 --port 8081"]
