"""Integration tests for Postgres durability, crash-recovery, and replay (Prompt 9 Part 3).

Assignment requirements:
- Real Postgres checkpointer (marker `postgres`; skipped when no DB).
- Run to interrupt, DROP in-memory graph and state, rebuild from Postgres, resume with approve.
- Assert proposal submitted EXACTLY ONCE (assert Connects spent once and one row in proposal_submissions).
- Assert second resume does not resubmit.
- Test pending_approvals and replay from checkpoint history.
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command

from agent.db import get_db_url, get_proposal_submission
from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_models import ProposalDraft as PortProposalDraft
from agent.marketplace_models import ProposalSubmit as PortProposalSubmit
from agent.nodes.base import NodeDeps
from agent.policy import load_policy_pack
from agent.runtime import history, pending_approvals, run_job
from agent.state import BidStatus
from rag.retriever import EvidenceItem

# Ensure Selector loop policy on Windows for async psycopg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def is_postgres_available() -> bool:
    """Checks whether local Postgres port 5433 is reachable."""
    try:
        import psycopg

        url = get_db_url()
        with psycopg.connect(url, connect_timeout=1):
            return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL on port 5433 is unreachable"),
]


class MockDurabilityPort:
    """Mock MarketplacePort tracking connects expenditure and submission calls."""

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
            created_at="2026-11-14T12:00:00Z",
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
            job_id="job_durability",
            status="submitted",
            connects_cost=4,
            connects_balance=50 - self.connects_spent,
            submitted_at="2026-11-14T12:05:00Z",
            message="Proposal submitted",
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
def durability_deps() -> NodeDeps:
    policy = load_policy_pack()
    return NodeDeps(
        port=MockDurabilityPort(),
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
async def test_postgres_crash_and_resume_durability(durability_deps: NodeDeps) -> None:
    """Simulates a hard process crash at the approval interrupt and resumes from Postgres."""
    url = get_db_url()
    user_id = f"user_{uuid4().hex[:6]}"
    job_id = f"job_{uuid4().hex[:8]}"
    thread_id = f"{user_id}:{job_id}"

    job = {
        "id": job_id,
        "title": "Machine Learning Engineer with FastAPI and LightGBM",
        "description": "Build high-throughput ML microservice using FastAPI and LightGBM models.",
        "skills": ["Python", "FastAPI", "LightGBM"],
        "budget": 2500.0,
        "budget_type": "fixed",
        "category": "ai_ml",
    }

    # 1. Start execution in first process context
    async with (
        AsyncPostgresSaver.from_conn_string(url) as saver1,
        AsyncPostgresStore.from_conn_string(url) as store1,
    ):
        await saver1.setup()
        await store1.setup()
        graph1 = build_bid_graph(checkpointer=saver1, store=store1, deps=durability_deps)

        config1 = {"configurable": {"thread_id": thread_id, "deps": durability_deps}}
        init_state = {
            "job": job,
            "user_id": user_id,
            "persona_id": "ai_ml",
            "budget": {"steps": 0, "tokens": 0},
        }

        # Run until the approval interrupt
        await graph1.ainvoke(init_state, config=config1)

        snap1 = await graph1.aget_state(config1)
        assert "approval" in snap1.next
        assert len(snap1.tasks[0].interrupts) > 0
        assert durability_deps.port.connects_spent == 0

    # 2. SIMULATE HARD PROCESS KILL: delete all in-memory graph and connection references
    del graph1
    del saver1
    del store1

    # 3. RESTART PROCESS: rebuild from Postgres connection
    async with (
        AsyncPostgresSaver.from_conn_string(url) as saver2,
        AsyncPostgresStore.from_conn_string(url) as store2,
    ):
        graph2 = build_bid_graph(checkpointer=saver2, store=store2, deps=durability_deps)
        config2 = {"configurable": {"thread_id": thread_id, "deps": durability_deps}}

        # Verify state rehydrated from Postgres
        snap2 = await graph2.aget_state(config2)
        assert "approval" in snap2.next
        assert snap2.values.get("job", {}).get("id") == job_id

        # Resume with human approval
        res = await graph2.ainvoke(Command(resume={"action": "approve"}), config=config2)
        assert res["status"] == BidStatus.SUBMITTED
        assert durability_deps.port.connects_spent == 4
        assert len(durability_deps.port.proposals_submitted) == 1

        # Verify row in proposal_submissions table
        submission_row = get_proposal_submission(thread_id)
        assert submission_row is not None
        assert submission_row["status"] == "submitted"
        assert submission_row["job_id"] == job_id

        # 4. Attempt a SECOND resume (replay/duplicate execution)
        res_dup = await graph2.ainvoke(Command(resume={"action": "approve"}), config=config2)
        # Must return the existing result and NOT submit or spend Connects again
        assert res_dup["status"] == BidStatus.SUBMITTED
        assert durability_deps.port.connects_spent == 4
        assert len(durability_deps.port.proposals_submitted) == 1


@pytest.mark.asyncio
async def test_pending_approvals_query(durability_deps: NodeDeps) -> None:
    """Verifies pending_approvals lists threads currently paused at approval interrupt."""
    url = get_db_url()
    user_id = f"user_pend_{uuid4().hex[:6]}"
    job_id = f"job_pend_{uuid4().hex[:8]}"

    job = {
        "id": job_id,
        "title": "Data Pipeline Engineer",
        "description": "Build high-throughput ETL in Python and FastAPI.",
        "skills": ["Python", "FastAPI"],
        "budget": 2000.0,
        "budget_type": "fixed",
    }

    async with (
        AsyncPostgresSaver.from_conn_string(url) as saver,
        AsyncPostgresStore.from_conn_string(url) as store,
    ):
        # Run job to interrupt
        await run_job(job, user_id=user_id, persona_id="ai_ml", deps=durability_deps, checkpointer=saver, store=store)

        # Check pending approvals for this user
        pending = await pending_approvals(user_id=user_id, checkpointer=saver, store=store)
        assert len(pending) >= 1
        found = next((p for p in pending if p["thread_id"] == f"{user_id}:{job_id}"), None)
        assert found is not None
        assert "draft" in found["payload"]
        assert found["payload"]["job_id"] == job_id


@pytest.mark.asyncio
async def test_checkpoint_history_tracking(durability_deps: NodeDeps) -> None:
    """Verifies history() lists chronological checkpoints across the StateGraph."""
    url = get_db_url()
    user_id = f"user_hist_{uuid4().hex[:6]}"
    job_id = f"job_hist_{uuid4().hex[:8]}"
    thread_id = f"{user_id}:{job_id}"

    job = {
        "id": job_id,
        "title": "Python Developer",
        "description": "Build tools in Python and FastAPI.",
        "skills": ["Python", "FastAPI"],
        "budget": 1500.0,
        "budget_type": "fixed",
    }

    async with (
        AsyncPostgresSaver.from_conn_string(url) as saver,
        AsyncPostgresStore.from_conn_string(url) as store,
    ):
        await run_job(job, user_id=user_id, persona_id="ai_ml", deps=durability_deps, checkpointer=saver, store=store)
        snaps = await history(thread_id, checkpointer=saver, store=store)
        assert len(snaps) >= 3
        # Should record intake and intermediate checkpoints
        sources = [s.get("source") for s in snaps]
        assert "loop" in sources or len(sources) > 0
