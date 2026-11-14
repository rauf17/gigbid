"""Typed graph state and reducers for the GigBid autonomous bidding pipeline.

THE THREE-WAY SPLIT (Assignment Architecture Requirement):
1. STATE (In-Flight Working Memory):
   Captured in `BidGraphState`. Contains only what the current thread needs right
   now to progress through the StateGraph. Kept lean to ensure checkpoints remain
   lightweight and fast to serialize.
2. EXECUTION TRACE (Audit & Observability):
   Every node transition, tool call, args, raw result, and observation is written
   append-only to the `audit_trace` table in PostgreSQL (or in-memory fallback).
   PII (emails, phone numbers, auth tokens) is strictly masked before insertion.
   Execution traces are NEVER stored in state.
3. LONG-TERM MEMORY (Cross-Thread Knowledge):
   Stored exclusively in the LangGraph Store under promoted namespaces
   (('style', user_id), ('outcome', user_id, category)). Only explicitly promoted,
   deduplicated, non-contradicted insights are written via promotion rules. Raw tool
   outputs, transient prompts, and unvetted drafts never enter long-term memory.
"""
from __future__ import annotations

import operator
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from agent.handoffs import (
    BidDecision,
    ComplianceVerdict,
    Critique,
    FitReport,
    JobSpec,
    PriceQuote,
    ProposalDraft,
    RiskReport,
    VerificationReport,
)


class BidStatus(StrEnum):
    """Lifecycle status enum for the bid state machine."""

    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUBMITTED = "submitted"
    SKIPPED = "skipped"
    WATCHING = "watching"
    REJECTED = "rejected"
    NEEDS_ATTENTION = "needs_attention"
    DEAD_LETTER = "dead_letter"


def reduce_budget(left: dict[str, int] | None, right: dict[str, int] | None) -> dict[str, int]:
    """Reducer that accumulates steps and token usage across parallel branches."""
    base = dict(left or {"steps": 0, "tokens": 0})
    if right:
        base["steps"] = base.get("steps", 0) + right.get("steps", 0)
        base["tokens"] = base.get("tokens", 0) + right.get("tokens", 0)
    return base


class BidGraphState(TypedDict, total=False):
    """Typed state for the autonomous freelance bidding StateGraph.

    Separates in-flight execution parameters from external audit logs and long-term memory.
    """

    # Core job context
    job: dict[str, Any]
    user_id: str
    persona_id: str
    trace_id: str

    # Assessment hand-offs (populated by parallel branches)
    spec: JobSpec | None
    risk: RiskReport | None
    fit: FitReport | None

    # Decision & economics
    decision: BidDecision | None
    quote: PriceQuote | None
    skip_reason: str | None

    # Proposal drafting & verification
    draft: ProposalDraft | None
    verification: VerificationReport | None
    critiques: Annotated[list[Critique], operator.add]
    compliance: ComplianceVerdict | None

    # Review, approval, and submission
    dry_run_preview: dict[str, Any] | None
    approval: dict[str, Any] | None
    outcome: dict[str, Any] | None

    # Loop guards and resource budgets
    revision_count: int
    budget: Annotated[dict[str, int], reduce_budget]
    status: str

    # Long-term memory inputs
    style_notes: str | None
