# GigBid Operations & Deployment Runbook (Part E6, R10)

This runbook documents production packaging, local multi-service orchestration via Docker Compose, deployment of the single-container Hugging Face Space, operations, and reviewer demo paths.

---

## 1. Local Deployment with Docker Compose

Every service in the GigBid architecture has its own dedicated Dockerfile under `infra/docker/`.

### Prerequisites & Setup
1. Copy `.env.example` to `.env` (never commit `.env`):
   ```bash
   cp .env.example .env
   ```
2. Configure required environment keys in `.env`:
   - `GROQ_API_KEY`: Groq API key for the open model profile (`openai/gpt-oss-20b` and `openai/gpt-oss-120b`).
   - `REVIEWER_EMAIL` & `REVIEWER_PASSWORD`: Reviewer credentials seeded on startup.
   - `APP_SECRET_KEY` & `TOKEN_ENCRYPTION_KEY`: Cryptographic signing and Fernet encryption keys.

### Start the Multi-Service Stack
```bash
# Build images and start all services in the background
docker compose -f infra/docker-compose.yml up --build -d

# Check service health and logs
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs -f api
```

### Services & Port Mappings
| Service | Internal Port | Host Port | Role |
| :--- | :---: | :---: | :--- |
| **web** | `3000` | `3000` | Next.js 14 App Router frontend (proxies `/api` to `api:8000`) |
| **api** | `8000` | `8000` | FastAPI backend, auth, SSE event streaming, approvals |
| **worker** | — | — | Arq asynchronous worker for background scouting & analysis |
| **portfolio-mcp** | `8001` | `8001` | Portfolio evidence discovery & case study MCP server |
| **marketplace-mcp** | `8002` | `8002` | Multi-tenant marketplace tool adapter MCP server |
| **gigsim** | `8081` | `8081` | Synthetic Upwork marketplace simulator |
| **postgres** | `5432` | `5433` | PostgreSQL 17 (app state, LangGraph checkpointer, memory) |
| **redis** | `6379` | `6380` | Redis 7 queue for Arq worker jobs |
| **ollama** *(optional)* | `11434` | `11434` | Local LLM host (`--profile local-llm`) |

To stop the stack:
```bash
docker compose -f infra/docker-compose.yml down
```

---

## 2. Packaging & Deployment Architecture

GigBid packages the entire multi-agent stack into two deployment formats:
1. **Multi-Service Docker Compose** (`infra/docker-compose.yml`): Runs individual services (`web`, `api`, `worker`, `marketplace-mcp`, `portfolio-mcp`, `gigsim`, `postgres`, `redis`) with isolated networking and healthchecks.
2. **Single-Container Lean Image** (`infra/docker/space.Dockerfile`): Process manager (`supervisord`) orchestrates all services within one container on port 7860 with Next.js proxying `/api` traffic to FastAPI.

### Hosting & Deployment Status
- **Local & Docker Verification**: The single-container `gigbid-space` image builds cleanly and runs locally (`docker run --rm -p 7860:7860 --env-file .env gigbid-space`). It has been verified end-to-end with zero mocks via `python scripts/live_smoke.py http://localhost:7860` and Playwright live E2E specs.
- **Public Hosting**: Evaluated for Hugging Face Spaces free-tier container deployment. Due to persistent storage and outbound egress constraints without payment cards on public clouds, production execution is maintained locally and via the reproducible `gigbid-space` Docker image.

### Build-Time Optimizations (Fast Cold Starts)
The single-container image bakes all static and model assets at build time:
- **CPU Torch Only**: Lightweight CPU wheel (~180 MB instead of ~2.5 GB CUDA bundle).
- **Pre-downloaded Models**: Sentence-transformers embeddings (`BAAI/bge-small-en-v1.5`) and reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) cached in `/root/.cache/huggingface`.
- **Pre-baked RAG Index**: Portfolio chunks, metadata manifests, and BM25 indexes generated via `make data` and `make ingest`.
- **Pre-compiled Next.js**: Production assets compiled via `npm run build` during image construction.

Cold start on boot takes **under 5 seconds** because zero network downloads are performed during boot.

---

## 3. Tracing & Observability (LangSmith, Requirement E3)

GigBid integrates LangSmith for distributed multi-agent trace visualization, debugging, and audit logging.

### Configuration
Tracing is enabled by setting `LANGSMITH_API_KEY` in `.env`:
```bash
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=gigbid
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```
If `LANGSMITH_API_KEY` is omitted, tracing is silently turned off with zero overhead, ensuring test suites and CI run without external network dependencies.

### End-to-End Trace Flow & PII Masking
1. **Trace ID Propagation**: `X-Trace-Id` header is received by FastAPI middleware (or generated as a UUID) and passed to:
   - Graph run metadata (`run_id`, `thread_id`, `job_id`, `persona`, `hashed_user_id`, `node_models`)
   - `MarketplacePort` MCP client headers (`X-Trace-Id`)
   - PostgreSQL `audit_trace` durable log rows
   - LangSmith run tags and metadata
2. **PII Masking**: All emails, phone numbers, crypto wallet addresses, credit cards, and IBAN numbers are automatically redacted using `agent.pii.mask_pii_obj` via the LangSmith client `anonymizer` hook before telemetry leaves the host.

### Generating Canonical Trace Examples
Run the trace generator script against the live stack:
```bash
python scripts/make_trace_examples.py
```
This generates four distinct execution traces:
- **(a) Skipped scam job**: Risk assessor triggers policy block on contact info and off-platform payment; decision node emits `skip`.
- **(b) Approved proposal**: Clean job triggers retrieval, drafting, claim verification, editorial critique, compliance, and approval interrupt; resumed with human approval.
- **(c) Critic revision loop**: Proposal flagged for generic phrasing or brevity triggers iterative revision edge back to writer before acceptance.
- **(d) Crash-and-resume**: Graph execution interrupted at human approval survives simulated process crash and successfully resumes from Postgres checkpointer.

*Note*: Public share links for evaluation reports can be published manually via the LangSmith UI ("Share" button on each run).

---

## 3. Operations & Known Limits

### Ephemeral Storage
- Hugging Face Spaces operate with ephemeral root filesystems on container restart.
- PostgreSQL state and pending approvals reset if the container restarts or reboots.
- Pre-baked data (jobs, persona portfolio evidence, BM25 indices) is permanently preserved in the container layers.

### Inactivity Sleep
- Free-tier Spaces sleep after 48 hours of inactivity.
- On wakeup, the entrypoint script automatically re-runs database migrations and seeds the reviewer account in $<5$ seconds.

### Autonomous Scouting Interval: 15m (Sim) vs. 180m (Live)
- **Simulator Mode (15 min)**: Accelerated event simulation where market ticks advance simulated hours in minutes.
- **Live Upwork Mode (180 min / 3 hours)**:
  1. *Rate Limiting*: Prevents IP bans and GraphQL search quota exhaustion.
  2. *Connects Budget Preservation*: Avoids spending weekly Connects on marginal listings before descriptions stabilize.
  3. *Cost & Latency*: Minimizes background LLM triage token spend while ensuring proposals enter client inboxes within the first 12 hours.

---

## 4. Reviewer Demo Walkthrough Path

Follow this path to evaluate the end-to-end platform in under 3 minutes:

1. **Sign In**:
   - Navigate to `/login`.
   - Enter `reviewer@gigbid.local` / `REVIEWER_PASSWORD`.
2. **Reviewer Persona Onboarding**:
   - Navigate to `/onboarding`.
   - Inspect persona cards (`ai_ml`, `fullstack`, `data_analyst`).
   - Select **AI & Machine Learning Engineer** and click **Continue to Inbox**.
3. **Opportunity Triage & Scam Filtering**:
   - On `/inbox`, review ingested opportunities.
   - Observe calibrated **Fit Match Score** (e.g. 94%), **Client Trust Score** (96%), and scam detection flags (e.g. 98% on planted Telegram scam).
   - Click **Open Studio →** on `job_001` (*Production Time-Series Forecasting Pipeline with LightGBM*).
4. **Proposal Studio & Factual Grounding**:
   - On `/studio/job_001`, observe the evidence-grounded proposal draft.
   - Hover over the inline evidence pill `[E:ai_ml_cs_cs_aiml_001]` to trigger the **`EvidenceHover`** popover displaying verified portfolio case study metrics (98% accuracy, sub-50ms latency).
5. **Human-in-the-Loop Review & Compliance Gating**:
   - Click **✏️ Edit Draft**.
   - Type an off-platform contact phrase: `Contact me on telegram @worker for payment`.
   - Click **Save Changes** → Notice immediate **Policy Pack Compliance Warning** banner.
   - Clean the edit and save.
   - Click **Reject Proposal...** → Observe the confirmation button remains **disabled** until feedback is entered in the textarea.
   - Click **Approve & Submit Bid** → Observe status transitions to **Submitted** and approval badge displays.
6. **Pipeline Kanban & State Progression**:
   - Navigate to `/pipeline`.
   - Observe the opportunity transitioned to the **Submitted** column.
   - Click **Advance Simulation (Tick)** to advance marketplace state.
7. **Trace Inspection**:
   - Navigate to `/runs/run_demo_001` to view the step-by-step **`RunTimeline`** graph execution trace.
