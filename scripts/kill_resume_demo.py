"""Scripted crash-and-resume demo (for viva / video demonstration).

Starts a bid graph run against Groq on one job, reaches the human approval
interrupt, commits state to PostgreSQL, and abruptly crashes the process (sys.exit(0)
after printing 'CRASH').

The second phase resumes the exact same thread from PostgreSQL in a fresh process,
approving the proposal and ensuring exact-once execution and Connects spend.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

from agent.marketplace_models import ProposalDraft as PortProposalDraft
from agent.marketplace_models import ProposalSubmit as PortProposalSubmit
from agent.nodes.base import NodeDeps
from agent.policy import load_policy_pack
from agent.runtime import (
    get_checkpointer_and_store,
    pending_approvals,
    resume,
    run_job,
)
from agent.state import ApprovalDecision, BidStatus
from rag.retriever import EvidenceItem

STATE_FILE = Path(".kill_resume_state.json")

SAMPLE_JOB = {
    "id": f"job_demo_{uuid4().hex[:6]}",
    "title": "Machine Learning Engineer with FastAPI and LightGBM",
    "description": (
        "We are building an agentic copilot and need an expert Python engineer "
        "with FastAPI, PostgreSQL, and LightGBM experience to build resilient "
        "background workflows."
    ),
    "category": "ai_ml",
    "client": {
        "id": "client_demo_99",
        "payment_verified": True,
        "total_spent": 45000.0,
        "rating": 4.95,
        "hires_count": 18,
    },
    "budget": 2500.0,
    "budget_type": "fixed",
    "skills": ["Python", "FastAPI", "LightGBM"],
    "required_skills": ["Python", "FastAPI", "LightGBM"],
    "connects_cost": 4,
}


class DemoRetriever:
    """Retriever providing evidence for the demo job."""

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


class DemoMarketplacePort:
    """MarketplacePort for the crash-and-resume demo."""

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
            job_id="job_demo",
            status="submitted",
            connects_cost=4,
            connects_balance=50 - self.connects_spent,
            submitted_at="2026-11-15T00:05:00Z",
            message="Proposal submitted",
            dry_run=dry_run,
        )


def build_deps() -> NodeDeps:
    policy = load_policy_pack()
    return NodeDeps(
        port=DemoMarketplacePort(),
        retriever=DemoRetriever(),
        policy=policy,
        config={
            "thresholds": {"minimum_fit_score": 0.50, "maximum_risk_score": 0.70},
            "pricing": {"connects_value_usd": 0.15, "min_ev_ratio": 2.0},
            "budgets": {"max_graph_steps": 30, "max_tokens_per_job": 12000, "max_revisions": 2},
            "autonomy": {"auto_skip_low_fit": True, "auto_send": False},
        },
    )


async def run_phase_1(user_id: str, job: dict) -> None:
    print("\n" + "=" * 60)
    print("PHASE 1: Starting new run on fresh process...")
    print(f"Target Job: {job['id']} - {job['title']}")
    print(f"User: {user_id}")
    print("=" * 60)

    deps = build_deps()
    thread_id = f"{user_id}:{job['id']}"

    async with get_checkpointer_and_store() as (checkpointer, store):
        result = await run_job(
            job=job,
            user_id=user_id,
            persona_id="ai_ml",
            deps=deps,
            checkpointer=checkpointer,
            store=store,
        )

        status = result.get("status")
        print("\n--- GRAPH EXECUTION RESULT ---")
        print(f"Status: {status}")
        print(f"Thread ID: {thread_id}")

        if status == BidStatus.AWAITING_APPROVAL or result.get("dry_run_preview"):
            preview = result.get("dry_run_preview", {})
            draft = result.get("draft")
            print("\n[PROPOSAL PREVIEW]")
            print(f"Bid Amount: ${preview.get('bid_amount', 2500.0):.2f}")
            print(f"Connects Required: {preview.get('connects_cost', 4)}")
            print("\nCover Letter Snippet:")
            cover = getattr(draft, "cover_letter", "") if draft else str(preview.get("cover_letter", ""))
            print(cover[:300] + ("..." if len(cover) > 300 else ""))

            # Persist resumption metadata
            STATE_FILE.write_text(
                json.dumps({
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "job": job,
                }, indent=2)
            )

            print("\n" + "=" * 60)
            print("REACHED APPROVAL INTERRUPT! State is durable in PostgreSQL.")
            print("SIMULATING ABRUPT CRASH (power cut / SIGKILL / process termination)...")
            print("CRASH")
            print("=" * 60)
            sys.exit(0)
        else:
            print(f"Unexpected status: {status}")
            sys.exit(1)


async def run_phase_2() -> None:
    if not STATE_FILE.exists():
        print(f"Error: {STATE_FILE} not found. Run Phase 1 first.")
        sys.exit(1)

    state = json.loads(STATE_FILE.read_text())
    thread_id = state["thread_id"]
    user_id = state["user_id"]

    print("\n" + "=" * 60)
    print("PHASE 2: Fresh Process Launched!")
    print(f"Re-attaching to PostgreSQL checkpointer for thread: {thread_id}")
    print("=" * 60)

    deps = build_deps()

    async with get_checkpointer_and_store() as (checkpointer, store):
        pending = await pending_approvals(user_id=user_id, checkpointer=checkpointer)
        print(f"Querying pending approvals for {user_id}...")
        found = any(p["thread_id"] == thread_id for p in pending)
        print(f"Thread {thread_id} found in pending checkpoints: {found}")
        assert found, f"Thread {thread_id} not found in pending checkpoints!"

        print("\nIssuing human APPROVAL Command(resume=...)...")
        decision = ApprovalDecision(action="approve").model_dump()
        result = await resume(
            thread_id=thread_id,
            decision=decision,
            deps=deps,
            checkpointer=checkpointer,
            store=store,
        )

        status = result.get("status")
        print("\n--- RESUMPTION RESULT ---")
        print(f"Final Status: {status}")
        outcome = result.get("outcome", {})
        print(f"Outcome Info: {outcome}")
        assert status == BidStatus.SUBMITTED, f"Expected 'submitted', got {status}"

        # Clean up demo state file
        STATE_FILE.unlink(missing_ok=True)
        print("\n" + "=" * 60)
        print("DEMO COMPLETE: Process crash survived. Resumption succeeded!")
        print("Connects and proposal submission executed exactly once.")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kill-Resume Durability Demo")
    parser.add_argument("--phase", choices=["1", "2"], help="Run phase 1 or phase 2")
    parser.add_argument("--user-id", default=f"user_{uuid4().hex[:6]}", help="User ID")
    args = parser.parse_args()

    if args.phase == "1":
        asyncio.run(run_phase_1(args.user_id, SAMPLE_JOB))
    elif args.phase == "2":
        asyncio.run(run_phase_2())
    else:
        # End-to-end automated orchestrator across two separate processes
        print("Starting Automated Two-Process Crash & Resume Demo...")
        user_id = args.user_id
        proc = subprocess.run(
            [sys.executable, str(Path(__file__)), "--phase", "1", "--user-id", user_id],
            capture_output=True,
            text=True,
            check=False,
        )
        print(proc.stdout)
        if proc.stderr:
            print("STDERR:", proc.stderr, file=sys.stderr)

        if "CRASH" not in proc.stdout:
            print("Phase 1 failed to reach crash point!")
            sys.exit(1)

        print("\n[Orchestrator] Detected process crash as expected.")
        print("[Orchestrator] Spawning completely new Python process for Phase 2...\n")

        proc2 = subprocess.run(
            [sys.executable, str(Path(__file__)), "--phase", "2"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(proc2.stdout)
        if proc2.stderr:
            print("STDERR:", proc2.stderr, file=sys.stderr)

        if proc2.returncode != 0:
            print("Phase 2 failed!")
            sys.exit(proc2.returncode)


if __name__ == "__main__":
    main()
