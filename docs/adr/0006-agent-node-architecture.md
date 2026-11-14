# ADR 0006: Standalone Agent Node Architecture with Explicit Dependency Container (NodeDeps)

**Status:** accepted

## Context
Assignment requirements for the GigBid autonomous bidding platform emphasize multi-agent separation of concerns (C3), rigorous node-level evaluation (B4), deterministic safety policies (R5, R9), and open-weight model routing (R8).

Prior to orchestrating these agents in a state machine (LangGraph), we must define the execution contract, interface boundaries, and dependency management strategy for all agent nodes (`analyst`, `risk_assessor`, `fit_matcher`, `decision`, `pricing`, `writer`, `verifier`, `critic`, `compliance`).

Three architectural patterns were evaluated:
- **Option A: Monolithic ReAct / Tool-Calling Loop**: A single agent equipped with tools to fetch job details, query portfolio RAG, check risk, calculate pricing, and draft proposals in a conversational loop.
- **Option B: Direct Orchestrator Coupling**: Authoring agent nodes directly as LangGraph node functions tightly bound to a global LangGraph `StateGraph` dictionary and runtime context.
- **Option C: Decoupled Async Functions with Explicit Dependency Container (`NodeDeps`)**: Implementing each agent as a pure asynchronous function with the standardized signature:
  `async def run(state_slice: dict[str, Any], deps: NodeDeps) -> HandoffModel`

## Decision
We select **Option C: Decoupled Async Functions with Explicit Dependency Container (`NodeDeps`)**.

### Justification
1. **Isolated Node-Level Evaluability (B4)**:
   In Option B, evaluating a single stage (e.g. the risk assessor or claim verifier) requires instantiating the entire graph runtime, mocking state edges, and traversing intermediate nodes. Under Option C, each node is an independent function that can be benchmarked directly. Dedicated evaluation runners (`decision_eval.py`, `proposal_eval.py`, `injection_eval.py`) execute subsets of nodes directly, collecting granular metrics (Bid/Skip F1, Claim unsupported drop, Injection ASR) without graph overhead.
2. **Hermetic Testability & Zero Global State**:
   Nodes have no ambient state, singleton registries, or hidden environment lookups. All external interfaces are passed through `deps: NodeDeps`:
   - `deps.port`: Abstract `MarketplacePort` interface for marketplace data lookups.
   - `deps.retriever`: Persona-scoped RAG retriever.
   - `deps.llm`: LLM client override (enabling instant offline test doubles like `FakeChatModel`).
   - `deps.policy`: Structured machine policy rules (`data/policy_pack/policy.yaml`).
   - `deps.config`: Tunable parameters from `agent/config.yaml`.
   Unit tests (`tests/unit/test_nodes.py`) mock individual dependencies in fractions of a second without standing up network infrastructure.
3. **Pure Function Decision Gate**:
   The critical bid-or-skip decision gate (`agent/nodes/decision.py`) contains zero LLM calls. It is implemented as a deterministic mathematical function evaluating risk thresholds, fit floors, and Connects expected value (EV) equations. Keeping nodes decoupled ensures this boundary cannot be compromised by conversational LLM drift.
4. **Seamless Orchestration Wiring**:
   Decoupling node execution logic from graph orchestration makes the eventual LangGraph wiring (Prompt 9) trivial: graph nodes will simply invoke `await node.run(state, deps)` and return the typed hand-off to update the state channel.

## Consequences
- Every agent node conforms to the `async def run(state_slice: dict[str, Any], deps: NodeDeps) -> Handoff` contract.
- Hand-offs between nodes are strictly typed, frozen Pydantic V2 models (`agent/handoffs.py`) implementing `schema_version = "1.0"`.
- Untrusted marketplace data is explicitly delimited (`wrap_untrusted`) before entering LLM contexts.
- Node implementations live under `agent/nodes/`, completely isolated from simulator code (`gigsim/`) and future graph wiring (`agent/graphs/`).
