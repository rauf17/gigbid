# GigBid Operations & Runbook

This runbook outlines operational procedures, infrastructure setup, service lifecycle commands, scouting intervals, and degraded mode troubleshooting for the **GigBid** autonomous bidding platform.

---

## 1. Quickstart & Infrastructure

GigBid relies on containerized PostgreSQL (port `5433`) and Redis (port `6380`), isolating state from any host database instances.

```bash
# 1. Start Docker dependencies (PostgreSQL 17 on 5433, Redis 7 on 6380) and run migrations
make db-up

# 2. Stop dependencies when finished
make db-down
```

### Environment Configuration (`.env`)
Copy `.env.example` to `.env` (never commit `.env`):
```bash
# Reviewer account seeded on API startup
REVIEWER_EMAIL=reviewer@gigbid.local
REVIEWER_PASSWORD=your_reviewer_password

# Data stores
DATABASE_URL=postgresql+psycopg://gigbid:gigbid@localhost:5433/gigbid
REDIS_URL=redis://localhost:6380/0

# Encryption key for external credentials at rest
TOKEN_ENCRYPTION_KEY=your_fernet_32byte_base64_key
```

---

## 2. Service Stack Components

Run services in separate terminal windows:

| Service | Port | Launch Command | Role |
| :--- | :---: | :--- | :--- |
| **GigSim Simulator** | `8081` | `uv run python gigsim/seed.py` | Local synthetic Upwork marketplace |
| **Marketplace MCP** | `8002` | `make mcp-marketplace` | Multi-tenant marketplace tool adapter |
| **Portfolio MCP** | `8001` | `make mcp-portfolio` | Vector and hybrid retrieval tool server |
| **FastAPI Backend** | `8000` | `make api` | REST API, Auth, SSE stream, and Webhooks |
| **Arq Worker** | Background | `make worker` | Autonomous scouting, deduplication, analysis |

---

## 3. Reviewer Onboarding & Seeding

On startup, the FastAPI application inspects `REVIEWER_EMAIL` and `REVIEWER_PASSWORD`. If configured and the user does not exist:
- Creates `usr_reviewer` with persona `ai_ml`.
- Hashes password using salted `bcrypt`.
- Initializes a default user profile with 40 weekly Connects and 50.0 hourly rate.

You can immediately log in as the reviewer:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "reviewer@gigbid.local", "password": "your_reviewer_password"}'
```

---

## 4. Autonomous Scouting Intervals: Live Mode vs. Simulator Mode

The Arq background worker polls saved searches via `cron_scout_all`. The interval differs fundamentally between environments:

### Simulator Mode (Default: 15 minutes)
- **Rationale**: GigSim is an accelerated event simulation. Ticks advance simulated hours in minutes. A 15-minute polling window ensures candidate jobs are detected and triaged before clients hire competing simulated freelancers.

### Live Mode (Upwork Production: 180 minutes / 3 hours)
- **Rationale**:
  1. **Rate Limits & API Quotas**: Upwork official API and GraphQL search endpoints enforce strict tenant and IP rate limits. Polling every 3 hours avoids IP throttling and bot detection flags.
  2. **Connects Preservation**: Scraping too frequently leads to hasty bidding on boundary jobs. 3-hour windows allow client job descriptions to stabilize and batch-triage high-fit opportunities against the user's weekly Connects budget.
  3. **Cost Optimization**: Each scouted batch triggers RAG retrieval and LLM triage. A 180-minute cadence minimizes background token consumption while ensuring proposals are delivered within the critical first 12 hours of job posting.

---

## 5. Degraded Mode & Failure Recovery (R9 / A6)

If the Marketplace MCP server or GigSim is stopped or unreachable:
1. **Reads**: `GET /jobs`, `GET /jobs/{id}`, and `GET /proposals` return HTTP `503 Service Unavailable`:
   ```json
   {
     "error": "marketplace_unavailable",
     "retryable": true,
     "queued": false
   }
   ```
2. **Writes / New Runs**: `POST /runs` catches the connection failure, enqueues the `analyse_job` task to Redis/Arq with a deterministic idempotency key (`_job_id="analyse:{user_id}:{job_id}"`), and returns HTTP `503`:
   ```json
   {
     "error": "marketplace_unavailable",
     "retryable": true,
     "queued": true
   }
   ```
3. **Automatic Recovery**: Once the marketplace service recovers, the Arq worker retries queued jobs automatically. Worker restarts never duplicate analysis because `job_analysed:{user_id}:{job_id}` keys in Redis and `proposal_submissions` rows in Postgres ensure idempotent delivery.

---

## 6. Health Probes & Dead Letter Inspection

### Health Probes
```bash
# Basic liveness
curl http://localhost:8000/health

# Dependency diagnostics (Postgres, Redis, MCPs, LLM keys)
curl http://localhost:8000/health/dependencies
```

### Inspecting Failed Threads (Dead Letter)
If an unrecoverable failure occurs inside a LangGraph node, the state snapshot is written to PostgreSQL table `dead_letter`:
```sql
SELECT id, thread_id, node_name, error_type, error_message, created_at
FROM dead_letter
ORDER BY created_at DESC
LIMIT 10;
```
