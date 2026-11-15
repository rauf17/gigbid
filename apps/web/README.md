# GigBid Web Application (`apps/web`)

Responsive, evidence-grounded autonomous freelancer copilot UI built with **Next.js 14 (App Router)**, **TypeScript**, and **Tailwind CSS**.

---

## Architecture & Real API Contract

Every screen in the GigBid web application is wired directly to the live FastAPI backend (proxied via `next.config.js` rewrites at `/api/:path*` to `http://127.0.0.1:8000/:path*`):

1. **`/inbox` (Opportunity Inbox)**:
   - Endpoint: `GET /api/jobs`
   - Real candidate jobs ingested from GigSim via `MarketplacePort`.
   - If a job has not had a run executed yet, it displays status **"Not analysed"** with a 1-click **"Analyse"** button that starts a LangGraph run (`POST /api/runs`). It does NOT show a fit score, trust score, or scam badge.
   - Once analysed, shows real fit score, client trust score, scam badge (with detected reason), and button to open Studio.
   - Supports search (title/client), filter (All, Strong Match, Awaiting Review, Not Analysed), and sort (Newest, Fit, Budget).

2. **`/jobs/[id]` (Job Details)**:
   - Endpoint: `GET /api/jobs/{id}`
   - Full job specifications, extracted requirements, required skills, client reputation, and last run status.
   - "Generate Bid / Run Pipeline" button starts analysis for unanalysed jobs.

3. **`/studio/[id]` (Proposal Studio)**:
   - Endpoint: `GET /api/approvals/{thread_id}`
   - Real pending approval payload: evidence-grounded cover letter, screening answers, claim-to-evidence matrix, risk assessment, price recommendation, dry_run Connects preview, and critic/compliance verdicts.
   - Interactive `EvidenceHover` popovers display actual retrieved portfolio evidence chunks, metrics, and match scores.
   - Human review actions:
     * **Approve**: `POST /api/approvals/{thread_id}` (`{ action: "approve" }`) resumes graph and dispatches proposal.
     * **Edit**: `POST /api/approvals/{thread_id}` (`{ action: "edit", edited_text: "..." }`) re-runs compliance verification.
     * **Reject**: `POST /api/approvals/{thread_id}` (`{ action: "reject", reason: "..." }`) enforces mandatory rationale.

4. **`/runs/[id]` (Live Execution Trace)**:
   - Endpoint: Server-Sent Events (SSE) `GET /api/runs/{thread_id}/stream`
   - Real-time event streaming rendering node-by-node graph state transitions (`analyst` -> `risk_assessor` -> `fit_matcher` -> `writer` -> `verifier` -> `critic` -> `compliance` -> `approval`).

5. **`/pipeline` (Bidding Pipeline Kanban)**:
   - Endpoint: `GET /api/proposals`
   - 7 lifecycle columns: Drafted, Submitted, Viewed, Replied, Interview, Hired, Lost.
   - Simulation tick trigger: `POST /api/sim/tick` advances marketplace simulation and refreshes Kanban stages.

6. **`/messages` (Client Conversation Liaison)**:
   - Endpoints: `GET /api/messages`, `GET /api/messages/{id}/suggestion`, `POST /api/messages/{id}/reply`, `POST /api/messages/{id}/approve`
   - Displays real conversation threads and AI-assisted reply proposals.

7. **`/analytics` (Performance Analytics)**:
   - Endpoint: `GET /api/analytics`
   - Real PostgreSQL database aggregations: category win rates, connects expenditures vs hires, LLM inference accounting (model calls, token counts, USD spend, average latency), and human rejection reason attribution.

8. **`/settings` (Platform Policies & Memory)**:
   - Endpoints: `GET/PUT /api/profile`, `GET/DELETE /api/memory`
   - Manages autonomous bidding levels (`supervised`, `semi_autonomous`, `autonomous`), budget caps, and PostgreSQL long-term memory store.

---

## Production vs. Mock Mode

- **Production Mode (Default)**:
  * Active whenever `NEXT_PUBLIC_MOCK` is not set (e.g. in Hugging Face Space single-container image, Docker Compose, or standard production builds).
  * Never serves or imports mock fixtures on the production code path.
  * Silent fallbacks are strictly removed: network and API errors render explicit error banners with retry triggers. If health probes return HTTP 503, the degraded fallback banner is presented.
  * Logged-in user email and persona are fetched dynamically from `GET /api/auth/me`.

- **Mock Mode (`NEXT_PUBLIC_MOCK=1`)**:
  * For offline development and fast CI/CD validation without requiring live databases.
  * Prominent amber top banner displayed across every page:
    > `DEMO DATA - MOCK MODE ACTIVE (set NEXT_PUBLIC_MOCK=0 or start the backend to use live data)`

---

## Testing Commands

```bash
# Run type checker (noEmit)
npm run lint

# Build production bundle
npm run build

# Run Playwright end-to-end mock test suite (5 offline specs)
npm run test:e2e

# Run Playwright live end-to-end integration tests against running backend
npm run test:e2e:live
```
