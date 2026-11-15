# Portfolio MCP Server Service
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml README.md ./
RUN uv pip install --system --no-cache torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache -e .

COPY . .

# Bake models and index into image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" && \
    python data/scripts/gen_personas.py && \
    python data/scripts/prepare_jobs.py && \
    python -m rag.ingest --persona all

EXPOSE 8001

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/mcp | grep -E '200|400|401|405' || exit 1

CMD ["uvicorn", "mcp_servers.portfolio.server:app", "--host", "0.0.0.0", "--port", "8001"]
