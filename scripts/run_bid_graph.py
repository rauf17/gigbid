"""CLI runner for manual testing and live execution of the StateGraph bid graph.

Assignment requirements:
- Part 5 of Prompt 9.
- Usage: `python scripts/run_bid_graph.py --persona ai_ml --job-id job_hist_00001 [--approve]`
- Runs against Groq, streams events to console (node start, tokens, latency, handoffs).
- Pauses at approval interrupt if not `--approve`.
- Displays interactive prompt (a: approve, r: reject, e: edit).
- Resumes and prints final proposal and Connects balance.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

from agent.graphs.bid_graph import stream_bid
from agent.marketplace_models import ProposalDraft as PortProposalDraft
from agent.marketplace_models import ProposalSubmit as PortProposalSubmit
from agent.nodes.base import NodeDeps
from agent.policy import load_policy_pack
from agent.runtime import get_checkpointer_and_store, resume
from agent.state import ApprovalDecision, BidStatus
from rag.retriever import get_retriever

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_PATHS = [
    Path(__file__).resolve().parent.parent / "data" / "processed" / "jobs_historical.jsonl",
    Path(__file__).resolve().parent.parent / "data" / "processed" / "jobs_stream.jsonl",
]


class CliMarketplacePort:
    """Port interface connecting to GigSim or mock sandbox for CLI runs."""

    def __init__(self, connects_balance: int = 50) -> None:
        self.connects_balance = connects_balance
        self.connects_spent = 0
        self.submissions: list[dict[str, Any]] = []

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
            message="Draft preview created via CLI port",
        )

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> PortProposalSubmit:
        if not dry_run:
            self.connects_spent += 4
            self.connects_balance -= 4
        self.submissions.append({"id": proposal_id, "key": idempotency_key, "dry_run": dry_run})
        return PortProposalSubmit(
            id=proposal_id,
            job_id="job_cli",
            status="submitted",
            connects_cost=4,
            connects_balance=self.connects_balance,
            submitted_at="2026-11-15T00:05:00Z",
            message="Proposal submitted successfully",
            dry_run=dry_run,
        )


def find_job(job_id: str) -> dict[str, Any]:
    """Locates job by ID in historical or stream datasets, with fallback synthetic job."""
    for p in DATA_PATHS:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == job_id:
                        return data
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Skipping unparseable line in dataset: %s", exc)
                    continue

    logger.warning("Job '%s' not found in processed datasets. Using fallback template.", job_id)
    return {
        "id": job_id,
        "title": "Machine Learning Engineer - FastAPI & Model Deployment",
        "description": "Develop high-throughput inference APIs and ML pipelines using Python, FastAPI, and LightGBM.",
        "skills": ["Python", "FastAPI", "LightGBM"],
        "budget": 2500.0,
        "budget_type": "fixed",
        "category": "ai_ml",
        "connects_cost": 4,
    }


async def run_cli(persona: str, job_id: str, auto_approve: bool, user_id: str) -> None:
    job = find_job(job_id)
    port = CliMarketplacePort(connects_balance=50)

    try:
        retriever = get_retriever(persona=persona)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not initialize full vector retriever (%s), using mock.", exc)
        from tests.integration.test_durability import MockRetriever

        retriever = MockRetriever()

    deps = NodeDeps(
        port=port,
        retriever=retriever,
        policy=load_policy_pack(),
    )

    thread_id = f"{user_id}:{job['id']}"
    print("\n" + "=" * 65)
    print(f"GIGBID PIPELINE: Running job {job['id']} for persona [{persona}]")
    print(f"Title: {job.get('title')}")
    print(f"Budget: ${job.get('budget', 0)} ({job.get('budget_type', 'fixed')})")
    print("=" * 65 + "\n")

    async with get_checkpointer_and_store() as (checkpointer, store):
        # Stream bid events
        interrupted = False
        async for item in stream_bid(
            job=job,
            user_id=user_id,
            persona_id=persona,
            deps=deps,
            checkpointer=checkpointer,
            store=store,
        ):
            mode, payload = item
            if mode == "custom":
                evt = payload.get("event")
                node = payload.get("node")
                if evt == "node_start":
                    print(f"  --> [START] {node}...")
                elif evt == "node_end":
                    lat = payload.get("duration_ms", 0.0)
                    tok = payload.get("tokens", 0)
                    print(f"  <-- [DONE]  {node} ({lat:.1f}ms, {tok} tokens)")

        # Inspect state after run
        from agent.graphs.bid_graph import build_bid_graph

        compiled = build_bid_graph(checkpointer=checkpointer, store=store, deps=deps)
        snap = await compiled.aget_state({"configurable": {"thread_id": thread_id}})

        current_status = snap.values.get("status")
        if "approval" in snap.next or len(snap.tasks[0].interrupts) > 0:
            interrupted = True

        if not interrupted:
            print(f"\nGraph finished without approval interrupt. Final Status: {current_status}")
            if current_status == BidStatus.SKIPPED:
                print(f"Skip Reason: {snap.values.get('skip_reason')}")
            return

        # Approval interrupt reached
        print("\n" + "=" * 65)
        print("HUMAN-IN-THE-LOOP APPROVAL REQUIRED")
        print("=" * 65)
        draft = snap.values.get("draft")
        quote = snap.values.get("quote")
        bid_amt = getattr(quote, "bid_amount", 0.0) if quote else 0.0
        print(f"Proposed Bid Amount: ${bid_amt:.2f}")
        print(f"Connects Required:   4 (Current balance: {port.connects_balance})")
        print("\n[Cover Letter Preview]:")
        letter = getattr(draft, "cover_letter", "") if draft else ""
        print(letter)
        print("-" * 65)

        if auto_approve:
            print("\n--approve flag set: Auto-approving proposal...")
            decision = ApprovalDecision(action="approve").model_dump()
        else:
            action_input = input("\nAction ([a]pprove / [r]eject / [e]dit cover letter): ").strip().lower()
            if action_input.startswith("r"):
                r_reason = input("Enter rejection reason: ").strip() or "Rejected by user"
                decision = ApprovalDecision(action="reject", reason=r_reason).model_dump()
            elif action_input.startswith("e"):
                e_text = input("Enter replacement cover letter:\n").strip()
                decision = ApprovalDecision(action="edit", edited_text=e_text).model_dump()
            else:
                decision = ApprovalDecision(action="approve").model_dump()

        print("\nResuming StateGraph pipeline...")
        res = await resume(
            thread_id=thread_id,
            decision=decision,
            deps=deps,
            checkpointer=checkpointer,
            store=store,
        )

        final_st = res.get("status")
        print("\n" + "=" * 65)
        print(f"EXECUTION COMPLETED. Final Status: {final_st}")
        print(f"Connects Remaining: {port.connects_balance}")
        if final_st == BidStatus.SUBMITTED:
            print(f"Proposal ID: {res.get('outcome', {}).get('id')}")
            print(f"Submitted At: {res.get('outcome', {}).get('submitted_at')}")
        elif final_st == BidStatus.REJECTED:
            print(f"Rejection Reason: {res.get('skip_reason')}")
        print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="GigBid StateGraph CLI Runner")
    parser.add_argument("--persona", choices=["ai_ml", "fullstack", "data_analyst"], default="ai_ml")
    parser.add_argument("--job-id", default="job_hist_00001", help="Target job ID")
    parser.add_argument("--approve", action="store_true", help="Auto-approve without interactive prompt")
    parser.add_argument("--user-id", default="freelancer_01", help="User ID")
    args = parser.parse_args()

    asyncio.run(run_cli(args.persona, args.job_id, args.approve, args.user_id))


if __name__ == "__main__":
    main()
