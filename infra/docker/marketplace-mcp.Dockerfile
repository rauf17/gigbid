# Marketplace MCP Server Service
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
RUN uv pip install --system --no-cache -e .

COPY . .

EXPOSE 8082

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/mcp | grep -E '200|400|401|405' || exit 1

CMD ["uvicorn", "mcp_servers.marketplace.server:app", "--host", "0.0.0.0", "--port", "8002"]
