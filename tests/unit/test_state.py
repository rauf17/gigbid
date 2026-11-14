"""Unit tests for agent state and reducers (Prompt 9 Part 1)."""
from __future__ import annotations

from agent.handoffs import Critique
from agent.state import BidGraphState, BidStatus, reduce_budget


def test_reduce_budget() -> None:
    left = {"steps": 1, "tokens": 150}
    right = {"steps": 2, "tokens": 300}
    merged = reduce_budget(left, right)
    assert merged["steps"] == 3
    assert merged["tokens"] == 450


def test_bid_status_enum() -> None:
    assert BidStatus.RUNNING == "running"
    assert BidStatus.AWAITING_APPROVAL == "awaiting_approval"
    assert BidStatus.SUBMITTED == "submitted"
    assert BidStatus.SKIPPED == "skipped"
    assert BidStatus.WATCHING == "watching"
    assert BidStatus.REJECTED == "rejected"
    assert BidStatus.NEEDS_ATTENTION == "needs_attention"
    assert BidStatus.DEAD_LETTER == "dead_letter"


def test_bid_graph_state_instantiation() -> None:
    critique = Critique(
        grounding=0.9,
        personalization=0.85,
        length_ok=True,
        generic_opening=False,
        issues=[],
        verdict="accept",
    )
    state: BidGraphState = {
        "job": {"id": "job_01", "title": "Test Engineer"},
        "user_id": "user_01",
        "persona_id": "ai_ml",
        "trace_id": "trace_01",
        "status": BidStatus.RUNNING,
        "revision_count": 0,
        "budget": {"steps": 1, "tokens": 100},
        "critiques": [critique],
    }
    assert state["job"]["id"] == "job_01"
    assert len(state["critiques"]) == 1
    assert state["status"] == "running"
