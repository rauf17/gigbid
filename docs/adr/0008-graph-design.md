# ADR 0008: Bid Graph Orchestration, Durability Architecture, and State-Trace-Memory Split

**Status:** accepted

## Context
The GigBid freelancer copilot requires an autonomous yet strictly governed pipeline to evaluate incoming marketplace jobs, compute pricing economics, ground proposal claims in verified evidence, critique drafts, enforce compliance, and submit proposals upon human approval.

Key architectural challenges include:
1. Orchestration framework selection (LangGraph vs. raw `asyncio` vs. AutoGen/CrewAI).
2. Human-in-the-loop governance: ensuring proposals are NEVER submitted without explicit human approval.
3. Durability across process crashes, container restarts, and machine failures.
4. Clean separation of ephemeral in-flight state, execution observability logs, and long-term learning.

## Decisions

### 1. Framework: Hand-Written LangGraph `StateGraph`
We choose a **hand-written `StateGraph`** compiled directly with conditional routing edges, rejecting `create_react_agent` and `langgraph-supervisor`.
- **Determinism and Auditability**: Autonomous bidding involves financial transactions (Connects spend). An unconstrained ReAct loop or autonomous supervisor risks tool-calling hallucinations and unbounded retry loops. Hand-written graphs enforce a strict, auditable state machine (`intake` $\to$ parallel assessment $\to$ `decide` $\to$ `pricing` $\to$ `writer` $\to$ `verifier` $\to$ `critic` $\to$ `compliance` $\to$ `approval` $\to$ `submit`).
- **Why Not Raw `asyncio`**: While raw Python `asyncio` can coordinate async functions, it lacks built-in checkpoint serialization, state versioning, interrupt mechanics, and re-entrant resumption from arbitrary graph nodes.
- **Why Not AutoGen / CrewAI**: AutoGen and CrewAI lean heavily on multi-agent conversational chatter, which inflates token costs by $3\times$ to $5\times$, adds non-deterministic latency, and obscures claim-level verification and compliance enforcement.

### 2. The Three-Way Split: State vs. Audit Trace vs. Long-Term Memory
To prevent memory leaks, bloated checkpoints, and unvetted memory pollution, data is strictly partitioned into three independent tiers:
1. **State (`BidGraphState`) - Ephemeral Working Memory**:
   - Contains only what the current thread needs right now to progress through graph nodes (`job`, `spec`, `risk`, `fit`, `quote`, `draft`, `verification`, `critiques`, `compliance`).
   - Kept lightweight to minimize checkpoint serialization latency and Postgres storage footprint.
2. **Execution Trace (`audit_trace` PostgreSQL Table) - Observability**:
   - Append-only audit log recording every node transition, execution latency, token expenditure, and error observation.
   - PII (emails, phone numbers, auth tokens) is strictly masked before insertion.
   - Never stored in state; survives process restarts independently.
3. **Long-Term Memory (LangGraph `Store`) - Cross-Thread Knowledge**:
   - Resides exclusively in the LangGraph `BaseStore` under partitioned namespaces:
     - `("style", user_id)`: learned user preferences and editorial patterns.
     - `("outcome", user_id, category)`: historical win/reply rates by category.
   - Guarded by explicit **promotion rules**: candidates must be observed across $\ge 2$ distinct proposals without contradiction before promotion. Raw tool outputs and unvetted drafts never enter long-term memory.
   - User inspection and deletion API ensures complete user control (`list_memory`, `delete_memory_item`).

### 3. Human-in-the-Loop: First-Class `interrupt()` Primitive
We select LangGraph's native `interrupt()` primitive at the `approval` node:
- **Strict Autonomy Guard**: Autonomous proposal dispatch (`auto_send=True`) is strictly prohibited and guarded at graph compilation and runtime (`ValueError`).
- **Dry-Run Preview**: Prior to suspension, the port generates an idempotent preview (`dry_run=True`), giving the human reviewer the exact Connects cost, proposed bid, and groundable cover letter.
- **Clean Resumption**: Resumption is triggered via `Command(resume=decision)` supporting three human actions:
  - `approve`: proceeds immediately to `submit` node.
  - `reject`: terminates cleanly with `status=rejected`.
  - `edit`: applies human corrections, re-runs compliance verification, and records the diff for long-term style learning.

### 4. Durability Trade-Offs: PostgreSQL Checkpointer vs. In-Memory
- In development and CI, `AsyncPostgresSaver` persists full state snapshots at each graph superstep to PostgreSQL on port **5433**.
- A hard process termination (`kill -9`, power loss, container eviction) during human review loses zero state. Resuming processes rehydrate from Postgres and guarantee exact-once execution and Connects spend.
- Fallback to `MemorySaver` and `InMemoryStore` is retained for isolated unit test execution.

## Consequences
- Every state transition is durable, reproducible, and replayable from historical checkpoints.
- Autonomy is rigorously constrained: financial expenditure cannot occur without human sign-off.
- Checkpoints remain lean and fast because audit traces and long-term memory are decoupled from in-flight graph state.
