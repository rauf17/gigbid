# GigBid Tools Catalog

All external marketplace interactions in GigBid are strictly mediated through Model Context Protocol (MCP) servers using FastMCP and the Streamable HTTP transport. Agent graphs never communicate with external databases, APIs, or scraping scripts directly (Requirements R1 and A2).

---

## 1. Marketplace MCP Server (`marketplace`)

- **Host & Port**: `http://127.0.0.1:8002/mcp`
- **Transport**: Streamable HTTP (`POST /mcp` / SSE)
- **Authentication**: Bearer Token via `Authorization: Bearer <MARKETPLACE_MCP_TOKEN>` header (HTTP 401 on unauthorized access).
- **Rate Limit**: Per-user sliding-window rate limit (default 20 requests/minute, tracked via `X-User-Id` header).
- **Telemetry & Tracing**: Distributed tracing via `X-Trace-Id` header with automatic append-only SQLite audit logging and PII masking.

### Tool Registry Table

| Tool Name | Server | Read / Write | Annotations | Auth | Owner | Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `search_jobs` | `marketplace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `scout` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `get_job` | `marketplace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `scout`, `risk_assessor`, `pricing`, `client_liaison`, `approval`, `submit` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `get_client_history` | `marketplace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `risk_assessor`, `pricing`, `client_liaison`, `approval`, `submit` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `get_connects_balance` | `marketplace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `pricing`, `approval`, `submit` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `list_messages` | `marketplace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `client_liaison` | `mcp_servers/marketplace/tests/test_server.py` |
| `create_proposal_draft` | `marketplace` | Write | `readOnlyHint=false`<br>`destructiveHint=false`<br>`idempotentHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `approval`, `submit` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `submit_proposal` | `marketplace` | Write | `readOnlyHint=false`<br>`destructiveHint=true`<br>`idempotentHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `approval`, `submit` | `mcp_servers/marketplace/tests/test_server.py`<br>`tests/integration/test_marketplace_gigsim.py` |
| `send_message` | `marketplace` | Write | `readOnlyHint=false`<br>`destructiveHint=true`<br>`idempotentHint=true` | Bearer (`MARKETPLACE_MCP_TOKEN`) | `client_liaison` | `mcp_servers/marketplace/tests/test_server.py` |

---

## 2. Tool Usage Guidance & Constraints

### 2.1 `search_jobs`
- **When to use**: During initial candidate sourcing by the `scout` agent to retrieve active job postings matching category, keyword queries, and publication timestamps.
- **When NOT to use**: Do NOT use if the target `job_id` is already known (use `get_job` instead). Do NOT use to draft or submit bids.
- **Constraints**: `limit` between 1 and 50; `query` max 200 characters.

### 2.2 `get_job`
- **When to use**: To inspect full requirements, client-stated budget, Connects cost, and tagged skills of a single job.
- **When NOT to use**: Do NOT use for general discovery without a specific job identifier.
- **Constraints**: `job_id` 3–64 characters matching `^[A-Za-z0-9_-]+$`.

### 2.3 `get_client_history`
- **When to use**: During risk evaluation (`risk_assessor`) and pricing calibration (`pricing`) to review client lifetime spend, hire rate, ratings, and payment verification status.
- **When NOT to use**: Do NOT use for analyzing job scope or writing cover letters.
- **Constraints**: `client_id` 3–64 characters matching `^[A-Za-z0-9_-]+$`.

### 2.4 `get_connects_balance`
- **When to use**: To check available Connects before recommending or scheduling proposals.
- **When NOT to use**: Do NOT poll in tight loops. Query once during evaluation.

### 2.5 `list_messages`
- **When to use**: In `client_liaison` conversations to review previous messages, interview requests, and client clarification questions.
- **When NOT to use**: Do NOT use on closed proposals or when submitting first-touch bids.

### 2.6 `create_proposal_draft`
- **When to use**: Persists a structured draft proposal or preview Connects cost with `dry_run=True`. Never charges Connects.
- **When NOT to use**: Do NOT use during initial job scouting or without an approved cover letter. Does NOT submit the proposal.
- **Constraints**: `bid_amount > 0` and `<= 500000.0`; `idempotency_key` 8–128 characters.

### 2.7 `submit_proposal`
- **When to use**: Final human-approved submission phase (`approval` / `submit`) to spend Connects and submit a proposal.
- **When NOT to use**: Destructive operation: spends real Connects. Never invoke automatically without policy checks or approval.
- **Constraints**: `idempotency_key` 8–128 characters (re-transmissions with same key return cached outcome without double charge).

### 2.8 `send_message`
- **When to use**: Client negotiation or follow-up messaging in existing threads.
- **When NOT to use**: Do NOT use for initial proposal submission.
- **Constraints**: `text` 1–5000 characters; `idempotency_key` 8–128 characters.

---

## 3. Portfolio MCP Server (`portfolio`)

- **Host & Port**: `http://127.0.0.1:8001/mcp` (or stdio mode via `gigbid-portfolio-mcp --stdio`)
- **Transport**: Streamable HTTP (`POST /mcp`) and stdio
- **Authentication**: Optional Bearer Token via `PORTFOLIO_MCP_TOKEN` (HTTP 401 on unauthorized access when configured; unauthenticated in local dev; bypassed in stdio mode).
- **Context Routing**: Persona dynamically switched via `X-Persona` HTTP header (defaults to `PORTFOLIO_PERSONA` env var, fallback `ai_ml`).

### Tool Registry Table

| Tool Name | Server | Read / Write | Annotations | Auth | Owner | Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `search_evidence` | `portfolio` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Optional Bearer (`PORTFOLIO_MCP_TOKEN`) | `evidence_gatherer`, `proposal_writer` | `mcp_servers/portfolio/tests/test_portfolio.py`<br>`tests/contract/test_portfolio_schema_snapshot.py` |
| `get_case_study` | `portfolio` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Optional Bearer (`PORTFOLIO_MCP_TOKEN`) | `evidence_gatherer`, `proposal_writer` | `mcp_servers/portfolio/tests/test_portfolio.py` |
| `list_skills` | `portfolio` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Optional Bearer (`PORTFOLIO_MCP_TOKEN`) | `scout`, `evidence_gatherer` | `mcp_servers/portfolio/tests/test_portfolio.py` |

### Tool Usage Guidance & Constraints

#### `search_evidence`
- **When to use**: During evidence collection to retrieve top-k matching portfolio chunks (case studies, code excerpts, past winning proposals, reviews) for a job requirement.
- **When NOT to use**: Do NOT use if you already have the specific case study ID (use `get_case_study` instead).
- **Constraints**: `requirement` 3–500 characters; `k` between 1 and 20 (default 5); `filters` by type, skills, and proposal outcome.

#### `get_case_study`
- **When to use**: Deep inspection of a specific past project narrative, client industry, and outcomes when citing an evidence proof point.
- **When NOT to use**: Do NOT use for keyword search across all artifacts (use `search_evidence`).
- **Constraints**: `id` string identifier (e.g. `cs_01`).

#### `list_skills`
- **When to use**: Fast qualification check to see if the active persona claims required technical skills, with counts of backing evidence items.
- **When NOT to use**: Do NOT use to inspect project text.

### Resource Templates
- `portfolio://case/{id}`: Returns the full case study markdown text for URI-based browsing.
- `portfolio://proposal/{id}`: Returns historical proposal text and outcome status.

### Prompt Templates
- `Answer a screening question from my portfolio`: Guides the model to search evidence and cite verifiable IDs without hallucinating experience.
- `Summarise my most relevant experience for this job`: Guides the model to retrieve top 3 evidence items matching a target job description.

---

## 4. Workspace MCP Server (`workspace`)

- **Host & Port**: `http://127.0.0.1:8003/mcp` (or stdio mode via `uv run python -m mcp_servers.workspace.server --stdio`)
- **Transport**: Streamable HTTP (`POST /mcp` / SSE) and stdio
- **Authentication**: Bearer Token via `Authorization: Bearer <WORKSPACE_MCP_TOKEN>` header (HTTP 401 on unauthorized access).
- **Backend Storage**: Local deterministic mock store (`mcp_servers/workspace/state/workspace_state.json`, gitignored) and SQLite audit log (`audit.db`).
- **Live API Status**: **Real Google Calendar and Gmail APIs are NOT wired (mock only).** Runs strictly over a local deterministic mock store for assignment compliance and sandbox isolation.

### Tool Registry Table

| Tool Name | Server | Read / Write | Annotations | Auth | Owner | Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `list_free_slots` | `workspace` | Read | `readOnlyHint=true`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Bearer (`WORKSPACE_MCP_TOKEN`) | `client_liaison` | `mcp_servers/workspace/tests/test_workspace.py`<br>`tests/contract/test_workspace_schema_snapshot.py` |
| `create_tentative_hold` | `workspace` | Write | `readOnlyHint=false`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Bearer (`WORKSPACE_MCP_TOKEN`) | `client_liaison`, `approval` | `mcp_servers/workspace/tests/test_workspace.py`<br>`tests/contract/test_workspace_schema_snapshot.py` |
| `create_email_draft` | `workspace` | Write | `readOnlyHint=false`<br>`idempotentHint=true`<br>`destructiveHint=false`<br>`openWorldHint=false` | Bearer (`WORKSPACE_MCP_TOKEN`) | `client_liaison` | `mcp_servers/workspace/tests/test_workspace.py`<br>`tests/contract/test_workspace_schema_snapshot.py` |

### Tool Usage Guidance & Constraints

#### `list_free_slots`
- **When to use**: When a client requests interview availability or asks for scheduling dates.
- **When NOT to use**: Do NOT use for general technical queries or first-touch bids.
- **Constraints**: `days_ahead` 1–14 (default 3); `duration_min` 15–120 (default 30).

#### `create_tentative_hold`
- **When to use**: To place a non-destructive tentative calendar hold on a free slot during client interview scheduling. Invoked **ONLY after human approval** of the message proposal.
- **When NOT to use**: Never call autonomously before human approval.
- **Constraints**: `slot_id` 3–64 chars; `title` 3–200 chars; `idempotency_key` up to 128 chars.

#### `create_email_draft`
- **When to use**: Preparing draft client follow-up correspondence.
- **When NOT to use**: In-platform marketplace chats (use `send_message` on marketplace port instead).
- **Constraints**: `to` valid email length; `subject` 1–200 chars; `body` 1–10,000 chars; `idempotency_key` up to 128 chars.

---

## 5. Tool Permissions & Allowlist

| Agent Role | Permitted Tools | Access Level |
| :--- | :--- | :--- |
| `scout` | `search_jobs`, `get_job`, `list_skills` | Read-only |
| `evidence_gatherer` | `search_evidence`, `get_case_study`, `list_skills` | Read-only |
| `proposal_writer` | `search_evidence`, `get_case_study` | Read-only |
| `risk_assessor` | `get_job`, `get_client_history` | Read-only |
| `pricing` | `get_job`, `get_client_history`, `get_connects_balance` | Read-only |
| `client_liaison` | `get_job`, `get_client_history`, `list_messages`, `send_message`, `search_evidence`, `list_free_slots`, `create_tentative_hold`, `create_email_draft` | Read + Messaging + Workspace Mock |
| `approval` / `submit` | `get_job`, `get_client_history`, `get_connects_balance`, `create_proposal_draft`, `submit_proposal`, `create_tentative_hold` | Full (Read + Destructive Write) |
