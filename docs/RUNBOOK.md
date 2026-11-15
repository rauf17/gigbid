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

## 2. Hugging Face Space Single-Container Deployment

GigBid packages the entire stack into a single lean container (`infra/docker/space.Dockerfile`) fitting within Hugging Face Space's free tier (2 vCPU / 16 GB RAM).

### Build-Time Optimizations (Fast Cold Starts)
The single-container image bakes all static and model assets at build time:
- **CPU Torch Only**: Lightweight CPU wheel (~180 MB instead of ~2.5 GB CUDA bundle).
- **Pre-downloaded Models**: Sentence-transformers embeddings (`BAAI/bge-small-en-v1.5`) and reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) cached in `/root/.cache/huggingface`.
- **Pre-baked RAG Index**: Portfolio chunks, metadata manifests, and BM25 indexes generated via `make data` and `make ingest`.
- **Pre-compiled Next.js**: Production assets compiled via `npm run build` during image construction.

Cold start on boot takes **under 5 seconds** because zero network downloads are performed during boot.

### Step-by-Step Space Creation
1. Go to [Hugging Face Spaces](https://huggingface.co/new-space) and create a new Space:
   - **Space Name**: `gigbid-copilot`
   - **License**: MIT
   - **Space SDK**: **Docker** (Blank template)
   - **Hardware**: Free (2 vCPU, 16 GB RAM)
2. In Space **Settings → Variables and Secrets**, add the following **Repository Secrets**:
   - `GROQ_API_KEY`: Your Groq API key.
   - `REVIEWER_EMAIL`: `reviewer@gigbid.local`
   - `REVIEWER_PASSWORD`: Strong reviewer password.
   - `TOKEN_ENCRYPTION_KEY`: 32-byte url-safe base64 key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
   - `APP_SECRET_KEY`: Random 32+ character hex string (`python -c "import secrets; print(secrets.token_hex(32))"`).
3. Push repository to the Space remote:
   ```bash
   git remote add space https://huggingface.co/spaces/<YOUR_HF_USERNAME>/gigbid-copilot
   git push space main
   ```
4. Access the public URL:
   `https://<YOUR_HF_USERNAME>-gigbid-copilot.hf.space`

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
