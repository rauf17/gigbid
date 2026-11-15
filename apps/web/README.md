# GigBid Web Application (`apps/web`)

Responsive, evidence-grounded autonomous freelancer copilot UI built with **Next.js 14 (App Router)**, **TypeScript**, and **Tailwind CSS**.

---

## Architecture & Features

1. **Proxy Rewrites & SSE Streaming**:
   - `next.config.js` configures `/api/:path*` proxying directly to the FastAPI backend (`http://127.0.0.1:8000/:path*`).
   - `compress: false` preserves unbuffered Server-Sent Events (SSE) streaming for real-time agent execution traces (`/runs/[id]/events`).

2. **Type Safety & OpenAPI Generation**:
   - Typed client contracts generated from `apps/api/openapi.json` via `openapi-typescript` into `src/lib/api/schema.d.ts`.
   - Reusable client library (`src/lib/client.ts`) providing unified access to Auth, Profile, Jobs, Proposals, Pipeline, and Runs.

3. **Autonomous Guardrails & Human-in-the-Loop Review**:
   - **`EvidenceHover`**: Interactive hover popovers that visually map cited evidence markers (e.g. `[E:ai_ml_cs_cs_aiml_001]`) to verified portfolio case studies, similarity scores, and quantitative metrics.
   - **`ApprovalPanel`**: Approval gateway ensuring proposals require explicit review before dispatch, mandatory rejection feedback capture for agent reinforcement, and live policy violation checks.
   - **`RunTimeline`**: Step-by-step audit visualization tracking LangGraph state transitions, execution latencies, and token spend.
   - **`DegradedBanner`**: Global status banner warning when backend health probes indicate 503 degraded fallback mode.

4. **10 Production Screens**:
   - `/login`: Form-based sign-in with session cookie and Bearer token handling.
   - `/onboarding`: Interactive freelancer persona selection (`ai_ml`, `fullstack`, `data_analyst`).
   - `/inbox`: Filterable opportunities table with calibrated match score, client trust, and scam alerts.
   - `/jobs/[id]`: Detailed job inspection with client breakdown, extracted requirements, and portfolio evidence.
   - `/studio/[id]`: Proposal studio with inline evidence preview, editing, and approval control.
   - `/pipeline`: 7-stage Kanban board with simulation advancement trigger (`POST /sim/tick`).
   - `/messages`: Client liaison threads with explicit policy-restriction notice (HTTP 501).
   - `/runs/[id]`: Trace inspector with live SSE event streaming.
   - `/analytics`: Conversion, win-rate, category outcomes, and rejection reason breakdown.
   - `/settings`: Autonomy mode, weekly budget caps, and Postgres long-term memory viewer.

---

## Development & Testing Commands

```bash
# Install dependencies
npm install

# Run type checker (noEmit)
npm run lint

# Generate API TypeScript types from OpenAPI spec
npm run generate:api

# Build production bundle
npm run build

# Start local server
npm run dev

# Run Playwright end-to-end test suite against Mock Mode
npm run test:e2e
```

## Mock Mode Configuration

Set `NEXT_PUBLIC_MOCK=1` in your environment or `.env.local` to run completely offline without requiring a running FastAPI or Postgres instance. All 5 Playwright specs run against mock mode for deterministic CI/CD validation.
