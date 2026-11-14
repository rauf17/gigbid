"""Unit tests for the hand-written StateGraph bid graph (Prompt 9 Part 2)."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_models import ProposalDraft as PortProposalDraft
from agent.marketplace_models import ProposalSubmit as PortProposalSubmit
from agent.nodes.base import NodeDeps
from agent.policy import load_policy_pack
from agent.state import BidStatus
from rag.retriever import EvidenceItem


class MockPort:
    """Mock port tracking draft creations and proposal submissions."""

    def __init__(self) -> None:
        self.drafts_created: list[dict[str, Any]] = []
        self.proposals_submitted: list[dict[str, Any]] = []

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: Any = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> PortProposalDraft:
        rec = {
            "job_id": job_id,
            "cover_letter": cover_letter,
            "bid_amount": bid_amount,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }
        self.drafts_created.append(rec)
        return PortProposalDraft(
            id=f"draft_{uuid4().hex[:8]}",
            job_id=job_id,
            cover_letter=cover_letter,
            bid_amount=bid_amount,
            connects_cost=4,
            status="draft",
            created_at="2026-11-14T12:00:00Z",
            dry_run=dry_run,
            message="Draft created",
        )

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> PortProposalSubmit:
        rec = {
            "proposal_id": proposal_id,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }
        self.proposals_submitted.append(rec)
        return PortProposalSubmit(
            id=proposal_id,
            job_id="job_test",
            status="submitted",
            connects_cost=4,
            connects_balance=46,
            submitted_at="2026-11-14T12:05:00Z",
            message="Submitted",
            dry_run=dry_run,
        )


class MockRetriever:
    """Mock retriever returning groundable evidence."""

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
def mock_deps() -> NodeDeps:
    policy = load_policy_pack()
    return NodeDeps(
        port=MockPort(),
        retriever=MockRetriever(),
        policy=policy,
        config={
            "thresholds": {"minimum_fit_score": 0.60, "maximum_risk_score": 0.70},
            "pricing": {"connects_value_usd": 0.15, "min_ev_ratio": 2.0},
            "budgets": {"max_graph_steps": 30, "max_tokens_per_job": 12000, "max_revisions": 2},
            "autonomy": {"auto_skip_low_fit": True, "auto_send": False},
        },
    )


@pytest.mark.asyncio
async def test_bid_graph_happy_path_to_interrupt_and_approve(mock_deps: NodeDeps) -> None:
    """Runs clean job through parallel intake to approval interrupt, then resumes with approve."""
    checkpointer = MemorySaver()
    graph = build_bid_graph(checkpointer=checkpointer, deps=mock_deps)

    job = {
        "id": "job_happy_01",
        "title": "Machine Learning Engineer with FastAPI and LightGBM",
        "description": "Build high-throughput ML microservice using FastAPI and LightGBM models.",
        "skills": ["Python", "FastAPI", "LightGBM"],
        "budget": 2500.0,
        "budget_type": "fixed",
        "category": "ai_ml",
    }

    thread_id = f"test_user_{uuid4().hex[:8]}:job_happy_01"
    config = {"configurable": {"thread_id": thread_id, "deps": mock_deps}}

    # 1. Run until approval interrupt
    _ = await graph.ainvoke(
        {
            "job": job,
            "user_id": "test_user_1",
            "persona_id": "ai_ml",
        },
        config=config,
    )

    state_snap = graph.get_state(config)
    assert "approval" in state_snap.next
    assert len(state_snap.tasks) > 0
    assert len(state_snap.tasks[0].interrupts) > 0
    payload = state_snap.tasks[0].interrupts[0].value
    assert payload["job_id"] == "job_happy_01"
    assert "draft" in payload
    assert "claims_matrix" in payload
    assert "price_rationale" in payload
    assert "dry_run_preview" in payload

    # Connects must NOT be spent prior to human approval
    port = mock_deps.port
    assert len(port.proposals_submitted) == 0

    # 2. Resume with approval
    final_res = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)

    assert final_res["status"] == BidStatus.SUBMITTED
    assert final_res["outcome"]["status"] == "submitted"
    assert len(port.proposals_submitted) == 1


@pytest.mark.asyncio
async def test_bid_graph_rejection(mock_deps: NodeDeps) -> None:
    """Verifies that rejecting at interrupt sets status to rejected and aborts submission."""
    checkpointer = MemorySaver()
    graph = build_bid_graph(checkpointer=checkpointer, deps=mock_deps)

    job = {
        "id": "job_reject_01",
        "title": "Python Developer",
        "description": "Build Python CLI tool.",
        "skills": ["Python"],
        "budget": 1000.0,
        "budget_type": "fixed",
    }
    thread_id = f"test_user_{uuid4().hex[:8]}:job_reject_01"
    config = {"configurable": {"thread_id": thread_id, "deps": mock_deps}}

    await graph.ainvoke({"job": job, "user_id": "test_user_1", "persona_id": "ai_ml"}, config=config)
    final_res = await graph.ainvoke(Command(resume={"action": "reject", "reason": "Rate too low"}), config=config)

    assert final_res["status"] == BidStatus.REJECTED
    assert final_res["skip_reason"] == "Rate too low"
    assert len(mock_deps.port.proposals_submitted) == 0


@pytest.mark.asyncio
async def test_bid_graph_edit_and_compliance_recheck(mock_deps: NodeDeps) -> None:
    """Verifies that user edits trigger diff tracking and compliance re-checking."""
    checkpointer = MemorySaver()
    graph = build_bid_graph(checkpointer=checkpointer, deps=mock_deps)

    job = {
        "id": "job_edit_01",
        "title": "FastAPI Developer",
        "description": "Build FastAPI service.",
        "skills": ["Python", "FastAPI"],
        "budget": 1500.0,
        "budget_type": "fixed",
    }
    thread_id = f"test_user_{uuid4().hex[:8]}:job_edit_01"
    config = {"configurable": {"thread_id": thread_id, "deps": mock_deps}}

    await graph.ainvoke({"job": job, "user_id": "test_user_1", "persona_id": "ai_ml"}, config=config)

    # Resume with edited text that violates policy (telegram handle)
    violating_edit = "I would love to help! Reach me on telegram @illegal_handle to chat."
    final_res = await graph.ainvoke(
        Command(resume={"action": "edit", "edited_text": violating_edit}),
        config=config,
    )

    assert final_res["status"] == BidStatus.NEEDS_ATTENTION
    assert "Compliance" in final_res["skip_reason"] or "compliance" in final_res["skip_reason"]
    assert len(mock_deps.port.proposals_submitted) == 0


@pytest.mark.asyncio
async def test_bid_graph_scam_skip_flow(mock_deps: NodeDeps) -> None:
    """Verifies scam jobs are routed to skipped status immediately after decide without pricing."""
    checkpointer = MemorySaver()
    graph = build_bid_graph(checkpointer=checkpointer, deps=mock_deps)

    scam_job = {
        "id": "job_scam_01",
        "title": "URGENT PAYMENT OUTSIDE",
        "description": "Send $50 deposit via cashapp or contact telegram @scammer. Do not apply on platform.",
        "skills": ["Python"],
        "client_id": "scam_client",
    }
    config = {"configurable": {"thread_id": "test_user:scam_01", "deps": mock_deps}}

    res = await graph.ainvoke(
        {"job": scam_job, "user_id": "test_user", "persona_id": "ai_ml"},
        config=config,
    )
    assert res["status"] in {BidStatus.SKIPPED, BidStatus.WATCHING, BidStatus.NEEDS_ATTENTION}
    assert res.get("quote") is None
    assert len(mock_deps.port.proposals_submitted) == 0


def test_bid_graph_autonomy_guard(mock_deps: NodeDeps) -> None:
    """Verifies that setting auto_send=True raises a strict policy error."""
    mock_deps.config["autonomy"]["auto_send"] = True
    with pytest.raises(ValueError, match=r"autonomous proposal submission \(auto_send\) is strictly prohibited"):
        build_bid_graph(deps=mock_deps)
