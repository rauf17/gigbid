# Single-Container Hugging Face Space Dockerfile (2 vCPU / 16 GB Lean CPU Build)
# Process Manager: Supervisord orchestrates Postgres, Redis, GigSim, MCPs, API, Worker, Next.js
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/root/.cache/huggingface \
    DATABASE_URL="postgresql+psycopg://gigbid:gigbid@127.0.0.1:5433/gigbid" \
    REDIS_URL="redis://127.0.0.1:6380/0" \
    GIGSIM_BASE_URL="http://127.0.0.1:8081" \
    PORTFOLIO_MCP_URL="http://127.0.0.1:8001/mcp" \
    MARKETPLACE_MCP_URL="http://127.0.0.1:8002/mcp" \
    MARKETPLACE_MODE="gigsim" \
    MODEL_PROFILE="open" \
    API_INTERNAL_URL="http://127.0.0.1:8000" \
    PORT="7860"

WORKDIR /app

# 1. System packages: PostgreSQL, Redis, Supervisor, Node.js 20, build utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql \
    postgresql-contrib \
    redis-server \
    supervisor \
    curl \
    make \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 from NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Configure PostgreSQL 15 cluster on port 5433 with trust authentication
RUN pg_dropcluster 15 main || true && \
    pg_createcluster 15 main --port 5433 && \
    echo "local all all trust" > /etc/postgresql/15/main/pg_hba.conf && \
    echo "host all all 127.0.0.1/32 trust" >> /etc/postgresql/15/main/pg_hba.conf && \
    echo "host all all ::1/128 trust" >> /etc/postgresql/15/main/pg_hba.conf

# Configure Redis port 6380
RUN sed -i 's/^port 6379/port 6380/' /etc/redis/redis.conf

# 2. Install uv and Python dependencies (Lean CPU torch)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml README.md ./

RUN uv pip install --system --no-cache torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache -e .

# 3. Pre-bake embedding model and reranker into Hugging Face cache
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('BAAI/bge-small-en-v1.5'); \
    CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# 4. Copy repository code
ENV PYTHONPATH="/app"
COPY . .

# 5. Bake data, seed database, and RAG index at build time
RUN python data/scripts/gen_personas.py && \
    python data/scripts/prepare_jobs.py && \
    python data/scripts/inject_adversarial.py && \
    python gigsim/seed.py && \
    python -m rag.ingest --persona all

# 6. Install frontend dependencies and bake Next.js production build
RUN cd apps/web && npm ci && npm run build

# 7. Configure supervisord and entrypoint
COPY infra/docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /app/infra/docker/entrypoint-space.sh && \
    mkdir -p /var/log/supervisor /var/run/postgresql && \
    chown -R postgres:postgres /var/run/postgresql

EXPOSE 7860

ENTRYPOINT ["/app/infra/docker/entrypoint-space.sh"]
