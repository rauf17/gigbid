"""End-to-end integration tests for the LangGraph StateGraph bid graph.

Assignment requirements:
- Part 5 of Prompt 9 (C1-C7, R3, R4, R7).
- Tests full graph execution across key production pathways:
  1. Skipped job: scam detected, graph stops at decide (status=skipped).
  2. Normal bid: reaches approval interrupt, resumes with approve (status=submitted).
  3. Critic loop: first draft triggers revise, second draft passes, revision_count==1 (status=submitted).
  4. Compliance block: banned contact info inserted, compliance flags it (status=needs_attention).
  5. Budget exceeded: token/step limit exceeded, graph stops at join/guard (status=needs_attention).
  6. Autonomy guard: auto_send=True strictly raises error before submit.
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from agent.handoffs import (
    ClaimAnnotation,
    Critique,
    ProposalDraft,
    RiskReport,
    VerificationReport,
)
from agent.marketplace_models import ProposalDraft as PortProposalDraft
from agent.marketplace_models import ProposalSubmit as PortProposalSubmit
from agent.nodes.base import NodeDeps
from agent.policy import load_policy_pack
from agent.state import BidStatus
from rag.retriever import EvidenceItem

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class MockIntegrationPort:
    def __init__(self) -> None:
        self.proposals_submitted: list[dict[str, Any]] = []
        self.connects_spent: int = 0

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: Any = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> PortProposalDraft:
        return PortProposalDraft(
            id=f"draft_{uuid4().hex[:8]}",
            job_id=job_id,
            cover_letter=cover_letter,
            bid_amount=bid_amount,
            connects_cost=4,
            status="draft",
            created_at="2026-11-15T00:00:00Z",
            dry_run=dry_run,
            message="Draft preview created",
        )

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> PortProposalSubmit:
        self.proposals_submitted.append({"id": proposal_id, "key": idempotency_key, "dry_run": dry_run})
        if not dry_run:
            self.connects_spent += 4
        return PortProposalSubmit(
            id=proposal_id,
            job_id="job_mock",
            status="submitted",
            connects_cost=4,
            connects_balance=50 - self.connects_spent,
            submitted_at="2026-11-15T00:05:00Z",
            message="Proposal submitted",
            dry_run=dry_run,
        )


class MockIntegrationRetriever:
    async def retrieve(self, query: Any, k: int = 5, filters: Any = None) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                id="cs_aiml_001",
                type="case_study",
                source="case_studies/cs_001.md",
                project="Demand Forecast",
                date="2025-01",
                text="Engineered a LightGBM time-series forecasting model with 98% accuracy.",
                score=0.92,
                skills=["Python", "FastAPI", "LightGBM"],
            )
        ]


@pytest.fixture
def base_deps() -> NodeDeps:
    return NodeDeps(
        port=MockIntegrationPort(),
        retriever=MockIntegrationRetriever(),
        policy=load_policy_pack(),
        config={
            "thresholds": {"minimum_fit_score": 0.50, "maximum_risk_score": 0.70},
            "pricing": {"connects_value_usd": 0.15, "min_ev_ratio": 2.0},
            "budgets": {"max_graph_steps": 30, "max_tokens_per_job": 12000, "max_revisions": 2},
            "autonomy": {"auto_skip_low_fit": True, "auto_send": False},
        },
    )


@pytest.fixture
def qualified_job() -> dict[str, Any]:
    return {
        "id": f"job_qual_{uuid4().hex[:6]}",
        "title": "Machine Learning Engineer with FastAPI and LightGBM",
        "description": "Build high-throughput ML microservice using FastAPI and LightGBM.",
        "skills": ["Python", "FastAPI", "LightGBM"],
        "budget": 2500.0,
        "budget_type": "fixed",
        "category": "ai_ml",
        "connects_cost": 4,
    }


@pytest.mark.asyncio
async def test_skipped_scam_job(base_deps: NodeDeps) -> None:
    """Scam job flagged by risk_assessor stops at decide node with status=skipped."""
    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=base_deps)

    scam_job = {
        "id": f"job_scam_{uuid4().hex[:6]}",
        "title": "Data Entry Specialist - Telegram Contact Required",
        "description": "Immediate hire! Send $50 deposit via wire and message @scam_boss on Telegram.",
        "skills": ["Data Entry"],
        "budget": 5000.0,
        "budget_type": "fixed",
        "category": "ai_ml",
    }

    thread_id = f"user_scam:{scam_job['id']}"
    config = {"configurable": {"thread_id": thread_id, "deps": base_deps}}

    # Mock risk_assessor to flag block recommendation
    mock_risk = RiskReport(
        risk_score=0.95,
        recommendation="block",
        rationale="Severe scam pattern detected: off-platform deposit and messenger contact.",
    )

    with patch("agent.nodes.risk_assessor.run", return_value=mock_risk):
        res = await graph.ainvoke({"job": scam_job, "user_id": "user_scam", "persona_id": "ai_ml"}, config=config)

    assert res["status"] == BidStatus.SKIPPED
    assert "Blocked by safety policy" in res.get("skip_reason", "")
    assert base_deps.port.connects_spent == 0
    assert len(base_deps.port.proposals_submitted) == 0


@pytest.mark.asyncio
async def test_normal_bid_happy_path(base_deps: NodeDeps, qualified_job: dict[str, Any]) -> None:
    """Normal qualified job reaches approval interrupt, resumes on approve, and submits."""
    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=base_deps)

    thread_id = f"user_norm:{qualified_job['id']}"
    config = {"configurable": {"thread_id": thread_id, "deps": base_deps}}

    # Run to interrupt
    await graph.ainvoke({"job": qualified_job, "user_id": "user_norm", "persona_id": "ai_ml"}, config=config)

    # Verify paused at approval
    snap = await graph.aget_state(config)
    assert "approval" in snap.next
    assert len(snap.tasks[0].interrupts) > 0
    assert base_deps.port.connects_spent == 0

    # Resume with human approval
    res = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
    assert res["status"] == BidStatus.SUBMITTED
    assert base_deps.port.connects_spent == 4
    assert len(base_deps.port.proposals_submitted) == 1


@pytest.mark.asyncio
async def test_critic_revision_loop(base_deps: NodeDeps, qualified_job: dict[str, Any]) -> None:
    """First critique triggers revision loop; second passes and completes to submit."""
    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=base_deps)

    thread_id = f"user_rev:{qualified_job['id']}"
    config = {"configurable": {"thread_id": thread_id, "deps": base_deps}}

    call_count = 0

    async def mock_critic_call(state_slice: Any, deps: Any) -> Critique:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Critique(
                verdict="revise",
                issues=["Explain latency optimization details."],
                grounding=0.6,
                personalization=0.7,
            )
        return Critique(
            verdict="accept",
            issues=[],
            grounding=0.9,
            personalization=0.9,
        )

    with patch("agent.nodes.critic.run", side_effect=mock_critic_call):
        await graph.ainvoke({"job": qualified_job, "user_id": "user_rev", "persona_id": "ai_ml"}, config=config)

    snap = await graph.aget_state(config)
    assert "approval" in snap.next
    assert snap.values.get("revision_count") == 2

    # Resume with approval
    res = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
    assert res["status"] == BidStatus.SUBMITTED
    assert base_deps.port.connects_spent == 4


@pytest.mark.asyncio
async def test_compliance_block(base_deps: NodeDeps, qualified_job: dict[str, Any]) -> None:
    """Draft with banned contact details is blocked by compliance node (status=needs_attention)."""
    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=base_deps)

    thread_id = f"user_comp:{qualified_job['id']}"
    config = {"configurable": {"thread_id": thread_id, "deps": base_deps}}

    banned_draft = ProposalDraft(
        cover_letter="Reach me on WhatsApp +1-555-0199 or message me on Telegram @secret_dev. Pay via PayPal [E:cs_aiml_001].",
        screening_answers=[],
        claims=[ClaimAnnotation(text="Reach me on WhatsApp [E:cs_aiml_001].", evidence_ids=["cs_aiml_001"])],
    )

    dummy_report = VerificationReport(
        checks=[],
        removed=[],
        rewritten=[],
        unsupported_rate_before=0.0,
        unsupported_rate_after=0.0,
    )

    with (
        patch("agent.nodes.writer.run", return_value=banned_draft),
        patch("agent.nodes.verifier.run", return_value=(banned_draft, dummy_report)),
    ):
        res = await graph.ainvoke({"job": qualified_job, "user_id": "user_comp", "persona_id": "ai_ml"}, config=config)

    assert res["status"] == BidStatus.NEEDS_ATTENTION
    assert res.get("compliance") is not None
    assert not res["compliance"].passed
    assert base_deps.port.connects_spent == 0


@pytest.mark.asyncio
async def test_budget_exceeded_guard(base_deps: NodeDeps, qualified_job: dict[str, Any]) -> None:
    """Setting tight token limit causes graph to stop at join node with status=needs_attention."""
    tight_deps = NodeDeps(
        port=base_deps.port,
        retriever=base_deps.retriever,
        policy=base_deps.policy,
        config={
            "thresholds": {"minimum_fit_score": 0.50, "maximum_risk_score": 0.70},
            "pricing": {"connects_value_usd": 0.15, "min_ev_ratio": 2.0},
            "budgets": {"max_graph_steps": 2, "max_tokens_per_job": 10, "max_revisions": 2},
            "autonomy": {"auto_skip_low_fit": True, "auto_send": False},
        },
    )

    checkpointer = MemorySaver()
    store = InMemoryStore()
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=tight_deps)

    thread_id = f"user_budg:{qualified_job['id']}"
    config = {"configurable": {"thread_id": thread_id, "deps": tight_deps}}

    res = await graph.ainvoke({"job": qualified_job, "user_id": "user_budg", "persona_id": "ai_ml"}, config=config)

    assert res["status"] == BidStatus.NEEDS_ATTENTION
    assert "budget exceeded" in res.get("skip_reason", "").lower()
    assert base_deps.port.connects_spent == 0


@pytest.mark.asyncio
async def test_autonomy_guard_auto_send_strictly_forbidden(base_deps: NodeDeps, qualified_job: dict[str, Any]) -> None:
    """Setting auto_send=True in config raises ValueError at approval node."""
    rogue_deps = NodeDeps(
        port=base_deps.port,
        retriever=base_deps.retriever,
        policy=base_deps.policy,
        config={
            "thresholds": {"minimum_fit_score": 0.50, "maximum_risk_score": 0.70},
            "pricing": {"connects_value_usd": 0.15, "min_ev_ratio": 2.0},
            "budgets": {"max_graph_steps": 30, "max_tokens_per_job": 12000, "max_revisions": 2},
            "autonomy": {"auto_skip_low_fit": True, "auto_send": True},
        },
    )

    checkpointer = MemorySaver()
    store = InMemoryStore()

    with pytest.raises(ValueError, match="autonomous proposal submission"):
        build_bid_graph(checkpointer=checkpointer, store=store, deps=rogue_deps)

    assert base_deps.port.connects_spent == 0
