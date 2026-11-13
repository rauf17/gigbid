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

## 3. Tool Permissions & Allowlist

| Agent Role | Permitted Tools | Access Level |
| :--- | :--- | :--- |
| `scout` | `search_jobs`, `get_job` | Read-only |
| `risk_assessor` | `get_job`, `get_client_history` | Read-only |
| `pricing` | `get_job`, `get_client_history`, `get_connects_balance` | Read-only |
| `client_liaison` | `get_job`, `get_client_history`, `list_messages`, `send_message` | Read + Messaging |
| `approval` / `submit` | `get_job`, `get_client_history`, `get_connects_balance`, `create_proposal_draft`, `submit_proposal` | Full (Read + Destructive Write) |
