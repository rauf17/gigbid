"""Hand-written StateGraph conversation graph for Client Liaison & Messaging.

Assignment Requirements (Parts A3 + C1, R5, R8, R9):
- Hand-written StateGraph (thread per client conversation).
- Pipeline: read_messages -> classify_intent -> draft_reply -> compliance -> approval (interrupt) -> send.
- Risk/safety rules evaluated first: scam_signal -> no reply drafted, flagged immediately.
- Interview requests: queries Workspace MCP list_free_slots and proposes slots in draft.
- Human-in-the-loop approval: interrupt() before send.
- Hold creation: create_tentative_hold is called ONLY AFTER human approval.
- Same checkpointer, store, budgets, and retry rules as bid graph.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import RetryPolicy, RunnableConfig, StreamWriter, interrupt
from typing_extensions import TypedDict

from agent.db import write_audit_trace
from agent.nodes.base import NodeDeps
from agent.nodes.client_liaison import (
    IntentClassification,
    classify_intent,
    draft_client_reply,
)
from agent.policy import load_policy_pack
from agent.workspace_client import MockWorkspaceClient, WorkspaceClient

logger = logging.getLogger(__name__)

DEFAULT_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=0.5,
    backoff_factor=2.0,
    jitter=True,
)


class ConversationGraphState(TypedDict, total=False):
    """State for client conversation and negotiation thread."""

    thread_id: str
    conversation_id: str
    user_id: str
    persona_id: str
    trace_id: str

    messages: list[dict[str, Any]]
    intent: str
    intent_classification: dict[str, Any]
    proposed_slots: list[dict[str, Any]]
    selected_slot_id: str | None

    draft_reply: str | None
    compliance_verdict: dict[str, Any] | None
    approval_payload: dict[str, Any] | None
    approval_decision: dict[str, Any] | None

    sent_message: dict[str, Any] | None
    held_slot: dict[str, Any] | None

    status: str  # reading | classified | drafting | awaiting_approval | replied | rejected | flagged_scam
    budget: dict[str, int]


def _get_active_deps(config: RunnableConfig | None, fallback: NodeDeps | None = None) -> NodeDeps:
    if config and "configurable" in config and "deps" in config["configurable"]:
        return config["configurable"]["deps"]
    return fallback or NodeDeps()


def _get_thread_id(config: RunnableConfig | None) -> str:
    if config and "configurable" in config and "thread_id" in config["configurable"]:
        return str(config["configurable"]["thread_id"])
    return "default_conversation_thread"


# -----------------------------------------------------------------------------
# Graph Nodes
# -----------------------------------------------------------------------------


async def node_read_messages(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Retrieves conversation message history from marketplace port if not already populated."""
    t0 = time.perf_counter()
    deps = _get_active_deps(config)
    conv_id = state.get("conversation_id", "conv_default")
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "read_messages"})

    messages = state.get("messages", [])
    if not messages and deps.port:
        try:
            raw_msgs = await deps.port.list_messages(conversation_id=conv_id)
            messages = [
                m.model_dump() if hasattr(m, "model_dump") else m.__dict__
                for m in raw_msgs
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed listing conversation messages: %s", exc)

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="read_messages",
        observation=f"Read {len(messages)} messages for conversation {conv_id}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "read_messages", "duration_ms": dur})
    return {
        "messages": messages,
        "status": "reading",
        "budget": {"steps": 1, "tokens": 0},
    }


async def node_classify_intent(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Classifies client intent into question | negotiation | interview_request | scam_signal."""
    t0 = time.perf_counter()
    deps = _get_active_deps(config)
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "classify_intent"})

    classification: IntentClassification = await classify_intent(
        messages=state.get("messages", []),
        deps=deps,
    )

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="classify_intent",
        observation=f"Classified intent={classification.intent} (conf={classification.confidence:.2f})",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "classify_intent", "duration_ms": dur})
    return {
        "intent": classification.intent,
        "intent_classification": classification.model_dump(),
        "status": "classified",
        "budget": {"steps": 1, "tokens": 0},
    }


def route_after_intent(state: ConversationGraphState) -> str:
    """Branches immediately to flag_scam if safety/risk rules trigger a scam_signal."""
    if state.get("intent") == "scam_signal":
        return "flag_scam"
    return "draft_reply"


async def node_flag_scam(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Safety stop: flags suspicious client message and drafts NO outbound reply."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "flag_scam"})

    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="flag_scam",
        observation="Scam signal detected. Blocked reply drafting and flagged conversation.",
        duration_ms=(time.perf_counter() - t0) * 1000.0,
    )
    writer({"event": "node_end", "node": "flag_scam", "flagged": True})
    return {
        "status": "flagged_scam",
        "draft_reply": None,
        "proposed_slots": [],
        "budget": {"steps": 1, "tokens": 0},
    }


async def node_draft_reply(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
    store: BaseStore | None = None,
) -> dict[str, Any]:
    """Drafts contextual response. Queries Workspace MCP list_free_slots for interview requests."""
    t0 = time.perf_counter()
    deps = _get_active_deps(config)
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "draft_reply"})

    intent = state.get("intent", "question")
    messages = state.get("messages", [])
    persona_id = state.get("persona_id", "ai_ml")

    # Read style memory from store if present
    style_notes: str | None = None
    if store is not None:
        try:
            user_id = state.get("user_id", "default_user")
            item = await store.aget(("style", user_id), "profile")
            if item and item.value:
                style_notes = str(item.value)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed reading style memory: %s", exc)

    draft_res = await draft_client_reply(
        intent=intent,
        messages=messages,
        deps=deps,
        persona_id=persona_id,
        style_memory=style_notes,
    )

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="draft_reply",
        observation=f"Drafted reply for {intent} with {len(draft_res.proposed_slots)} proposed slots",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "draft_reply", "duration_ms": dur})
    return {
        "draft_reply": draft_res.reply_text,
        "proposed_slots": draft_res.proposed_slots,
        "status": "drafting",
        "budget": {"steps": 1, "tokens": 0},
    }


async def node_compliance(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Ensures outbound message satisfies platform communication and contact exchange rules."""
    t0 = time.perf_counter()
    deps = _get_active_deps(config)
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "compliance"})

    reply_text = state.get("draft_reply", "")
    policy = deps.policy or load_policy_pack()

    violations: list[str] = []
    # Check off-platform patterns in draft
    for rule in policy.rules:
        if rule.id in ("POL-001", "POL-002", "POL-004"):
            for detector in rule.detector:
                if detector.type == "regex":
                    for pat in detector.patterns:
                        import re
                        if re.search(pat, reply_text, re.IGNORECASE):
                            violations.append(f"{rule.id}: {rule.description}")

    dur = (time.perf_counter() - t0) * 1000.0
    passed = len(violations) == 0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="compliance",
        observation=f"Compliance check passed={passed}, violations={len(violations)}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "compliance", "passed": passed})
    return {
        "compliance_verdict": {"passed": passed, "violations": violations},
        "status": "awaiting_approval",
        "budget": {"steps": 1, "tokens": 0},
    }


async def node_approval(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Suspends execution via interrupt() to present suggested reply and await human sign-off."""
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "approval"})

    payload = {
        "thread_id": thread_id,
        "conversation_id": state.get("conversation_id"),
        "intent": state.get("intent"),
        "intent_classification": state.get("intent_classification"),
        "draft_reply": state.get("draft_reply"),
        "proposed_slots": state.get("proposed_slots", []),
        "compliance": state.get("compliance_verdict"),
    }

    # Suspend execution until Command(resume=decision) is received
    decision_val = interrupt(payload)

    action = decision_val.get("action", "approve") if isinstance(decision_val, dict) else "approve"
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="approval",
        observation=f"Conversation approval resumed with action={action}",
    )
    writer({"event": "node_end", "node": "approval", "decision": decision_val})
    return {
        "approval_payload": payload,
        "approval_decision": decision_val if isinstance(decision_val, dict) else {"action": action},
        "budget": {"steps": 1, "tokens": 0},
    }


async def node_send(
    state: ConversationGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Sends approved message and creates tentative calendar hold for interview requests."""
    t0 = time.perf_counter()
    deps = _get_active_deps(config)
    thread_id = _get_thread_id(config)
    writer({"event": "node_start", "node": "send"})

    decision = state.get("approval_decision", {})
    action = decision.get("action", "approve")

    if action == "reject":
        write_audit_trace(
            trace_id=state.get("trace_id", ""),
            thread_id=thread_id,
            node_name="send",
            observation="Message rejected by reviewer. Nothing sent.",
            duration_ms=(time.perf_counter() - t0) * 1000.0,
        )
        writer({"event": "node_end", "node": "send", "sent": False})
        return {
            "status": "rejected",
            "sent_message": None,
            "budget": {"steps": 1, "tokens": 0},
        }

    # Final text: edited text if provided, otherwise original draft
    final_text = decision.get("edited_text") or state.get("draft_reply") or ""
    conv_id = state.get("conversation_id", "conv_default")
    idempotency_key = f"conv_msg_{thread_id}_{uuid4().hex[:8]}"

    sent_data: dict[str, Any] = {}
    if deps.port:
        try:
            sent_msg = await deps.port.send_message(
                conversation_id=conv_id,
                text=final_text,
                idempotency_key=idempotency_key,
            )
            sent_data = sent_msg.model_dump() if hasattr(sent_msg, "model_dump") else sent_msg.__dict__
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed sending message via port: %s", exc)
            sent_data = {"id": f"msg_{uuid4().hex[:8]}", "text": final_text, "status": "sent_fallback"}
    else:
        sent_data = {"id": f"mock_{uuid4().hex[:8]}", "text": final_text, "status": "mock_sent"}

    # If interview request: create tentative hold ONLY AFTER human approval
    held_slot_record: dict[str, Any] | None = None
    if state.get("intent") == "interview_request" and state.get("proposed_slots"):
        slots = state.get("proposed_slots", [])
        chosen_slot = slots[0]
        slot_id = chosen_slot.get("slot_id", "")
        ws_client: WorkspaceClient = deps.workspace_client or MockWorkspaceClient()
        try:
            held_slot_record = await ws_client.create_tentative_hold(
                slot_id=slot_id,
                title=f"Client Interview: {conv_id}",
                idempotency_key=f"hold_{thread_id}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed creating tentative hold: %s", exc)

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="send",
        observation=f"Message sent to {conv_id}. Hold created={bool(held_slot_record)}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "send", "sent": True, "duration_ms": dur})
    return {
        "status": "replied",
        "sent_message": sent_data,
        "held_slot": held_slot_record,
        "budget": {"steps": 1, "tokens": 0},
    }


# -----------------------------------------------------------------------------
# Graph Assembly
# -----------------------------------------------------------------------------


def build_conversation_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> CompiledStateGraph:
    """Builds and compiles the StateGraph for client liaison and conversations."""
    workflow = StateGraph(ConversationGraphState)

    workflow.add_node("read_messages", node_read_messages, retry_policy=DEFAULT_RETRY)
    workflow.add_node("classify_intent", node_classify_intent, retry_policy=DEFAULT_RETRY)
    workflow.add_node("flag_scam", node_flag_scam)
    workflow.add_node("draft_reply", node_draft_reply, retry_policy=DEFAULT_RETRY)
    workflow.add_node("compliance", node_compliance, retry_policy=DEFAULT_RETRY)
    workflow.add_node("approval", node_approval)
    workflow.add_node("send", node_send, retry_policy=DEFAULT_RETRY)

    workflow.add_edge(START, "read_messages")
    workflow.add_edge("read_messages", "classify_intent")

    workflow.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "flag_scam": "flag_scam",
            "draft_reply": "draft_reply",
        },
    )

    workflow.add_edge("flag_scam", END)
    workflow.add_edge("draft_reply", "compliance")
    workflow.add_edge("compliance", "approval")
    workflow.add_edge("approval", "send")
    workflow.add_edge("send", END)

    app_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(
        checkpointer=app_checkpointer,
        store=store,
    )
