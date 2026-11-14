"""Unit tests for long-term memory store and promotion rules.

Assignment requirements:
- candidate rule proposed once: NOT in long-term store.
- same pattern proposed second time: PROMOTED to long-term store.
- contradictory rule proposed: rejected, logged to audit.
- delete_memory_item removes it; subsequent list does not return it.
- writer node receives promoted style rules in its prompt input.
- outcome memory with Laplace smoothing.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from langgraph.store.memory import InMemoryStore

from agent.memory.promotion_rules import (
    compute_smoothed_outcome,
)
from agent.memory.store import (
    ExtractedRulePayload,
    delete_memory_item,
    get_style_notes_for_writer,
    get_style_rules,
    list_memory,
    record_outcome,
    record_proposal_edit,
)
from agent.nodes.base import NodeDeps
from agent.nodes.writer import run as writer_run


@pytest.fixture
def memory_store() -> InMemoryStore:
    return InMemoryStore()


@pytest.mark.asyncio
async def test_candidate_rule_proposed_once_not_in_store(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"

    mock_extracted = ExtractedRulePayload(
        has_rule=True,
        pattern_key="concise_bullets",
        rule_text="Limit technical approach to at most 3 concise bullet points.",
        polarity="positive",
        scope="cover_letter",
    )

    with patch("agent.memory.store.llm_call", return_value=mock_extracted):
        decision = await record_proposal_edit(
            user_id=user_id,
            original_text="Long paragraph without bullet points.",
            edited_text="Concise bullet points: 1. A, 2. B.",
            edit_id="edit_001",
            store=memory_store,
            deps=NodeDeps(config={"memory": {"min_observations": 2}}),
        )

    # Must NOT be promoted yet
    assert decision.promoted is False
    assert decision.observed_count == 1
    assert "Pending" in decision.reason

    # Long-term store must remain empty
    promoted = await get_style_rules(user_id, memory_store)
    assert len(promoted) == 0

    # Must be tracked in pending namespace
    pending_items = await memory_store.asearch(("pending_style", user_id))
    assert len(pending_items) == 1
    assert pending_items[0].value["pattern_key"] == "concise_bullets"


@pytest.mark.asyncio
async def test_same_pattern_second_time_promoted(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"

    mock_extracted = ExtractedRulePayload(
        has_rule=True,
        pattern_key="concise_bullets",
        rule_text="Limit technical approach to at most 3 concise bullet points.",
        polarity="positive",
        scope="cover_letter",
    )

    deps = NodeDeps(config={"memory": {"min_observations": 2}})

    with patch("agent.memory.store.llm_call", return_value=mock_extracted):
        # First observation
        d1 = await record_proposal_edit(
            user_id=user_id,
            original_text="Long text 1",
            edited_text="Bullet 1, Bullet 2",
            edit_id="edit_001",
            store=memory_store,
            deps=deps,
        )
        assert d1.promoted is False

        # Second observation on a distinct proposal
        d2 = await record_proposal_edit(
            user_id=user_id,
            original_text="Long text 2",
            edited_text="Bullet A, Bullet B",
            edit_id="edit_002",
            store=memory_store,
            deps=deps,
        )
        assert d2.promoted is True
        assert d2.observed_count == 2
        assert d2.rule is not None
        assert d2.rule.id == "rule_concise_bullets"
        assert set(d2.rule.source_edit_ids) == {"edit_001", "edit_002"}

    # Promoted rule must now exist in long-term store
    promoted = await get_style_rules(user_id, memory_store)
    assert len(promoted) == 1
    assert promoted[0].id == "rule_concise_bullets"
    assert promoted[0].count == 2

    # Pending store must be cleaned up
    pending_items = await memory_store.asearch(("pending_style", user_id))
    assert len(pending_items) == 0


@pytest.mark.asyncio
async def test_contradictory_rule_rejected_and_audited(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"
    deps = NodeDeps(config={"memory": {"min_observations": 2}})

    # Seed an already promoted rule mandating bullet points (positive polarity)
    await memory_store.aput(
        ("style", user_id),
        "rule_concise_bullets",
        {
            "id": "rule_concise_bullets",
            "rule_text": "Always format technical milestones using concise bullet points.",
            "pattern": "concise_bullets",
            "source_edit_ids": ["seed_1", "seed_2"],
            "count": 2,
            "created_at": "2026-11-15T00:00:00Z",
            "polarity": "positive",
        },
    )

    # Propose a contradictory candidate rule prohibiting bullet points (negative polarity)
    mock_contradictory = ExtractedRulePayload(
        has_rule=True,
        pattern_key="concise_bullets",
        rule_text="Never use bullet points in proposals; use narrative paragraphs only.",
        polarity="negative",
        scope="cover_letter",
    )

    with patch("agent.memory.store.llm_call", return_value=mock_contradictory):
        decision = await record_proposal_edit(
            user_id=user_id,
            original_text="Bullets: 1. A, 2. B",
            edited_text="Narrative paragraph text.",
            edit_id="edit_conflict",
            store=memory_store,
            deps=deps,
        )

    # Must be rejected due to contradiction
    assert decision.promoted is False
    assert decision.conflicting_rule_id == "rule_concise_bullets"
    assert "Contradicts existing promoted rule" in decision.reason

    # Existing rule remains uncorrupted
    promoted = await get_style_rules(user_id, memory_store)
    assert len(promoted) == 1
    assert promoted[0].rule_text == "Always format technical milestones using concise bullet points."


@pytest.mark.asyncio
async def test_delete_memory_item(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"

    # Add a style item
    await memory_store.aput(
        ("style", user_id),
        "rule_no_delighted",
        {
            "id": "rule_no_delighted",
            "rule_text": "Do not use the word 'delighted' in greetings.",
            "pattern": "no_delighted",
            "source_edit_ids": ["e1", "e2"],
            "count": 2,
            "created_at": "2026-11-15T00:00:00Z",
            "polarity": "negative",
        },
    )

    # Verify present
    items = await list_memory(user_id, namespace="style", store=memory_store)
    assert len(items) == 1
    assert items[0].key == "rule_no_delighted"

    # Delete item
    success = await delete_memory_item(user_id, namespace="style", key="rule_no_delighted", store=memory_store)
    assert success is True

    # Verify subsequent list does not return it
    items_after = await list_memory(user_id, namespace="style", store=memory_store)
    assert len(items_after) == 0


@pytest.mark.asyncio
async def test_writer_node_receives_promoted_style_rules(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"

    # Put promoted rule into store
    await memory_store.aput(
        ("style", user_id),
        "rule_brief_intro",
        {
            "id": "rule_brief_intro",
            "rule_text": "Keep introduction under two sentences and mention previous production SLA.",
            "pattern": "brief_intro",
            "source_edit_ids": ["e1", "e2"],
            "count": 2,
            "created_at": "2026-11-15T00:00:00Z",
            "polarity": "positive",
        },
    )

    # Test get_style_notes_for_writer
    notes = await get_style_notes_for_writer(user_id, memory_store)
    assert "Keep introduction under two sentences and mention previous production SLA." in notes

    # Test that writer node receives and incorporates style notes
    captured_vars: dict[str, Any] = {}

    def mock_writer_call(node: str, variables: dict[str, Any], schema: Any, model_override: Any = None) -> Any:
        nonlocal captured_vars
        captured_vars = variables
        from agent.handoffs import ProposalDraft

        return ProposalDraft(
            cover_letter="Sample proposal text [E:cs_01].",
            screening_answers=[],
            claims=[],
        )

    deps = NodeDeps()
    with patch("agent.nodes.writer.llm_call", side_effect=mock_writer_call):
        await writer_run(
            {
                "job_spec": {"title": "Python Engineer", "summary": "Build API"},
                "persona": "ai_ml",
                "evidence_items": [{"id": "cs_01", "text": "Built high throughput API"}],
                "style_notes": notes,
            },
            deps=deps,
        )

    assert "Keep introduction under two sentences" in captured_vars.get("job_post", "")


def test_outcome_memory_laplace_smoothing() -> None:
    # Under minimum outcomes (< 3): not promoted
    stats_low = compute_smoothed_outcome(category="ai_ml", bids=2, replies=1, hires=0, min_outcomes=3)
    assert stats_low is None

    # Reaching minimum outcomes (>= 3): promoted with Laplace smoothing
    # bids=3, hires=1 -> Laplace = (1 + 1) / (3 + 2) = 2/5 = 0.40
    stats = compute_smoothed_outcome(category="ai_ml", bids=3, replies=2, hires=1, min_outcomes=3)
    assert stats is not None
    assert stats.category == "ai_ml"
    assert stats.bids_count == 3
    assert stats.hires_count == 1
    assert stats.win_rate == pytest.approx(0.3333, abs=0.01)
    assert stats.smoothed_win_rate == 0.40


@pytest.mark.asyncio
async def test_record_outcome_end_to_end(memory_store: InMemoryStore) -> None:
    user_id = f"user_{uuid4().hex[:6]}"
    deps = NodeDeps(config={"memory": {"min_outcomes": 3}})

    # First bid - under threshold
    res1 = await record_outcome(user_id, "ai_ml", "bid", memory_store, deps)
    assert res1 is None

    # Second bid - under threshold
    res2 = await record_outcome(user_id, "ai_ml", "bid", memory_store, deps)
    assert res2 is None

    # Third bid with hire - reaches threshold
    res3 = await record_outcome(user_id, "ai_ml", "hire", memory_store, deps)
    assert res3 is not None
    assert res3.bids_count == 3
    assert res3.hires_count == 1
    assert res3.smoothed_win_rate == 0.40

    # Query store
    items = await list_memory(user_id, namespace="outcome", store=memory_store)
    assert len(items) == 1
    assert items[0].value["smoothed_win_rate"] == 0.40
