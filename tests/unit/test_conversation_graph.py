"""Unit tests for the hand-written StateGraph conversation graph (Prompt 13).

Covers:
- All intent routes: question, negotiation, interview_request, scam_signal.
- Safety check: scam_signal triggers immediately via risk rules and drafts/sends NOTHING.
- Autonomy check: graph interrupts at approval BEFORE sending any message.
- Workspace MCP check: interview holds created ONLY AFTER human approval.
- Durability check: resume executes and sends message exactly once.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graphs.conversation_graph import (
    ConversationGraphState,
    build_conversation_graph,
)
from agent.marketplace_models import Message
from agent.nodes.base import NodeDeps
from agent.workspace_client import MockWorkspaceClient


class FakeConversationPort:
    """Fake marketplace port tracking message interactions."""

    def __init__(self, initial_messages: list[dict[str, Any]] | None = None) -> None:
        self.messages_sent: list[dict[str, Any]] = []
        self.initial_messages = initial_messages or []

    async def list_messages(self, conversation_id: str) -> list[Message]:
        return [
            Message(
                id=m.get("id", f"msg_{uuid4().hex[:6]}"),
                conversation_id=conversation_id,
                sender=m.get("sender", m.get("sender_role", "client")),
                text=m.get("text", ""),
                created_at=m.get("created_at", "2026-11-15T12:00:00Z"),
            )
            for m in self.initial_messages
        ]

    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> Message:
        rec = {
            "conversation_id": conversation_id,
            "text": text,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }
        self.messages_sent.append(rec)
        return Message(
            id=f"msg_{uuid4().hex[:8]}",
            conversation_id=conversation_id,
            sender="freelancer",
            text=text,
            created_at="2026-11-15T12:05:00Z",
        )


class FakeWorkspaceClient(MockWorkspaceClient):
    """Fake workspace client tracking tool calls."""

    def __init__(self) -> None:
        super().__init__()
        self.list_slots_calls: list[dict[str, Any]] = []
        self.holds_created: list[dict[str, Any]] = []

    async def list_free_slots(self, days_ahead: int = 3, duration_min: int = 30) -> list[dict[str, Any]]:
        self.list_slots_calls.append({"days_ahead": days_ahead, "duration_min": duration_min})
        return [
            {
                "slot_id": "slot_20261116_1400",
                "start_time": "2026-11-16T14:00:00Z",
                "end_time": "2026-11-16T14:30:00Z",
                "duration_min": 30,
                "formatted": "Monday, Nov 16 at 02:00 PM - 02:30 PM UTC",
            },
            {
                "slot_id": "slot_20261117_1530",
                "start_time": "2026-11-17T15:30:00Z",
                "end_time": "2026-11-17T16:00:00Z",
                "duration_min": 30,
                "formatted": "Tuesday, Nov 17 at 03:30 PM - 04:00 PM UTC",
            },
        ]

    async def create_tentative_hold(
        self,
        slot_id: str,
        title: str,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        rec = {"slot_id": slot_id, "title": title, "idempotency_key": idempotency_key}
        self.holds_created.append(rec)
        return {
            "hold_id": f"hold_{uuid4().hex[:8]}",
            "slot_id": slot_id,
            "title": title,
            "status": "tentative",
            "start_time": "2026-11-16T14:00:00Z",
            "end_time": "2026-11-16T14:30:00Z",
            "held_at": "2026-11-15T12:00:00Z",
            "idempotency_key": idempotency_key,
        }


@pytest.mark.asyncio
async def test_question_intent_route_and_approval():
    """Client asks technical question: routes to draft_reply -> approval interrupt -> send on approve."""
    port = FakeConversationPort([
        {"sender_role": "client", "text": "What is your experience deploying vector databases with pgvector?"}
    ])
    deps = NodeDeps(port=port)
    checkpointer = MemorySaver()
    graph = build_conversation_graph(checkpointer=checkpointer)

    thread_id = "test_thread_question_1"
    config = {"configurable": {"thread_id": thread_id, "deps": deps}}

    # 1. First invocation: runs up to interrupt
    init_state: ConversationGraphState = {
        "thread_id": thread_id,
        "conversation_id": "conv_q1",
        "user_id": "user_1",
        "persona_id": "ai_ml",
        "trace_id": "tr_q1",
        "budget": {"steps": 0, "tokens": 0},
    }
    await graph.ainvoke(init_state, config=config)

    # Verify suspended before sending
    state = await graph.aget_state(config)
    assert "approval" in state.next or len(state.tasks) > 0
    assert state.values.get("intent") == "question"
    assert state.values.get("status") == "awaiting_approval"
    assert state.values.get("draft_reply") is not None
    assert len(port.messages_sent) == 0  # NOTHING sent before approval

    # 2. Resume with approval
    res = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
    assert res.get("status") == "replied"
    assert len(port.messages_sent) == 1
    assert "production-ready systems" in port.messages_sent[0]["text"]


@pytest.mark.asyncio
async def test_negotiation_intent_route_and_edit():
    """Client negotiates rates: routes to negotiation draft -> reviewer edits text -> sends edited text."""
    port = FakeConversationPort([
        {"sender_role": "client", "text": "Can you do $45/hr for this project instead?"}
    ])
    deps = NodeDeps(port=port)
    checkpointer = MemorySaver()
    graph = build_conversation_graph(checkpointer=checkpointer)

    thread_id = "test_thread_negotiation_2"
    config = {"configurable": {"thread_id": thread_id, "deps": deps}}

    init_state: ConversationGraphState = {
        "thread_id": thread_id,
        "conversation_id": "conv_neg2",
        "user_id": "user_1",
        "persona_id": "ai_ml",
        "trace_id": "tr_neg2",
        "budget": {"steps": 0, "tokens": 0},
    }
    await graph.ainvoke(init_state, config=config)

    state = await graph.aget_state(config)
    assert state.values.get("intent") == "negotiation"
    assert state.values.get("status") == "awaiting_approval"

    # Reviewer provides customized edit
    custom_text = "We can offer a fixed-price initial phase to prove capability within your budget."
    res = await graph.ainvoke(
        Command(resume={"action": "edit", "edited_text": custom_text}),
        config=config,
    )
    assert res.get("status") == "replied"
    assert len(port.messages_sent) == 1
    assert port.messages_sent[0]["text"] == custom_text


@pytest.mark.asyncio
async def test_interview_request_intent_route_holds_slot_after_approval():
    """Client requests interview: queries slots, proposes them, creates hold ONLY AFTER approval."""
    port = FakeConversationPort([
        {"sender_role": "client", "text": "We'd like to schedule a call this week. Are you available for a sync?"}
    ])
    ws_client = FakeWorkspaceClient()
    deps = NodeDeps(port=port, workspace_client=ws_client)
    checkpointer = MemorySaver()
    graph = build_conversation_graph(checkpointer=checkpointer)

    thread_id = "test_thread_interview_3"
    config = {"configurable": {"thread_id": thread_id, "deps": deps}}

    init_state: ConversationGraphState = {
        "thread_id": thread_id,
        "conversation_id": "conv_int3",
        "user_id": "user_1",
        "persona_id": "ai_ml",
        "trace_id": "tr_int3",
        "budget": {"steps": 0, "tokens": 0},
    }
    await graph.ainvoke(init_state, config=config)

    # Check state at interrupt
    state = await graph.aget_state(config)
    assert state.values.get("intent") == "interview_request"
    assert len(ws_client.list_slots_calls) == 1
    assert len(state.values.get("proposed_slots", [])) == 2
    # CRITICAL: Tentative hold must NOT be created before human approval
    assert len(ws_client.holds_created) == 0
    assert len(port.messages_sent) == 0

    # Resume with approval
    res = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
    assert res.get("status") == "replied"
    # Hold is created AFTER approval
    assert len(ws_client.holds_created) == 1
    assert ws_client.holds_created[0]["slot_id"] == "slot_20261116_1400"
    assert len(port.messages_sent) == 1
    assert "Monday, Nov 16" in port.messages_sent[0]["text"]


@pytest.mark.asyncio
async def test_scam_signal_intent_route_sends_nothing():
    """Safety test: message with Telegram/off-platform triggers scam_signal, flags thread, drafts/sends NOTHING."""
    port = FakeConversationPort([
        {"sender_role": "client", "text": "Please message our hiring lead on Telegram @techlead99 to receive payment."}
    ])
    ws_client = FakeWorkspaceClient()
    deps = NodeDeps(port=port, workspace_client=ws_client)
    checkpointer = MemorySaver()
    graph = build_conversation_graph(checkpointer=checkpointer)

    thread_id = "test_thread_scam_4"
    config = {"configurable": {"thread_id": thread_id, "deps": deps}}

    init_state: ConversationGraphState = {
        "thread_id": thread_id,
        "conversation_id": "conv_scam4",
        "user_id": "user_1",
        "persona_id": "ai_ml",
        "trace_id": "tr_scam4",
        "budget": {"steps": 0, "tokens": 0},
    }
    res = await graph.ainvoke(init_state, config=config)

    # Immediately reaches END in flagged_scam state
    assert res.get("intent") == "scam_signal"
    assert res.get("status") == "flagged_scam"
    assert res.get("draft_reply") is None
    assert len(res.get("proposed_slots", [])) == 0

    # Zero outbound messages sent
    assert len(port.messages_sent) == 0
    assert len(ws_client.holds_created) == 0


@pytest.mark.asyncio
async def test_restart_resume_sends_once():
    """Durability check: restarting and resuming sends exactly one message."""
    port = FakeConversationPort([
        {"sender_role": "client", "text": "Could you provide details on your team's background?"}
    ])
    deps = NodeDeps(port=port)
    checkpointer = MemorySaver()
    graph = build_conversation_graph(checkpointer=checkpointer)

    thread_id = "test_thread_restart_5"
    config = {"configurable": {"thread_id": thread_id, "deps": deps}}

    init_state: ConversationGraphState = {
        "thread_id": thread_id,
        "conversation_id": "conv_res5",
        "user_id": "user_1",
        "persona_id": "ai_ml",
        "trace_id": "tr_res5",
        "budget": {"steps": 0, "tokens": 0},
    }
    # Run to interrupt
    await graph.ainvoke(init_state, config=config)
    assert len(port.messages_sent) == 0

    # Re-compile graph simulating server restart
    restarted_graph = build_conversation_graph(checkpointer=checkpointer)
    state_before_resume = await restarted_graph.aget_state(config)
    assert state_before_resume.values.get("status") == "awaiting_approval"

    # Resume once
    res = await restarted_graph.ainvoke(Command(resume={"action": "approve"}), config=config)
    assert res.get("status") == "replied"
    assert len(port.messages_sent) == 1

    # Check state again: no second message sent
    final_state = await restarted_graph.aget_state(config)
    assert final_state.values.get("status") == "replied"
    assert len(port.messages_sent) == 1
