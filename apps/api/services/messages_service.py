"""Service layer for marketplace conversation threads and messaging."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from agent.marketplace_port import MarketplacePort, MarketplacePortError
from agent.nodes.base import NodeDeps
from agent.runtime import resume_conversation, run_conversation
from apps.api.deps import handle_marketplace_error
from apps.api.schemas.messages import (
    MessageItem,
    SuggestedReplyResponse,
    SuggestedSlotItem,
)

logger = logging.getLogger(__name__)


async def get_conversation_messages(conversation_id: str, port: MarketplacePort) -> list[MessageItem]:
    try:
        raw_msgs = await port.list_messages(conversation_id=conversation_id)
        return [
            MessageItem(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_id=m.sender_id,
                sender_role=m.sender_role,
                text=m.text,
                timestamp=m.timestamp,
            )
            for m in raw_msgs
        ]
    except (MarketplacePortError, httpx.HTTPError, OSError) as exc:
        handle_marketplace_error(exc, queued=False)
        return []


async def send_conversation_reply(
    conversation_id: str,
    text: str,
    port: MarketplacePort,
) -> MessageItem:
    try:
        msg = await port.send_message(conversation_id=conversation_id, text=text)
        return MessageItem(
            id=msg.id,
            conversation_id=msg.conversation_id,
            sender_id=msg.sender_id,
            sender_role=msg.sender_role,
            text=msg.text,
            timestamp=msg.timestamp,
        )
    except (MarketplacePortError, httpx.HTTPError, OSError) as exc:
        handle_marketplace_error(exc, queued=False)
        raise


async def get_or_create_conversation_suggestion(
    user_id: str,
    conversation_id: str,
    port: MarketplacePort,
    persona_id: str = "ai_ml",
) -> SuggestedReplyResponse:
    """Executes or advances conversation graph to generate suggested reply and free slots."""
    deps = NodeDeps(port=port)
    thread_id = f"conv:{user_id}:{conversation_id}"

    state = await run_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        persona_id=persona_id,
        deps=deps,
    )

    intent = state.get("intent", "question")
    draft = state.get("draft_reply")
    proposed_slots_raw = state.get("proposed_slots", [])
    slots = [
        SuggestedSlotItem(
            slot_id=s.get("slot_id", ""),
            start_time=s.get("start_time", ""),
            end_time=s.get("end_time", ""),
            duration_min=s.get("duration_min", 30),
            formatted=s.get("formatted", ""),
        )
        for s in proposed_slots_raw
    ]

    status = state.get("status", "awaiting_approval")
    comp = state.get("compliance_verdict", {})
    passed = bool(comp.get("passed", True))
    risk_flags = state.get("intent_classification", {}).get("risk_flags", [])

    detail = "Suggested reply generated."
    if intent == "scam_signal":
        detail = "Scam signal detected — outbound reply suppressed."

    return SuggestedReplyResponse(
        conversation_id=conversation_id,
        thread_id=thread_id,
        status=status,
        intent=intent,
        suggested_reply=draft,
        suggested_replies=[draft] if draft else [],
        proposed_slots=slots,
        is_awaiting_approval=(status == "awaiting_approval"),
        compliance_passed=passed,
        risk_flags=risk_flags,
        detail=detail,
    )


async def approve_conversation_suggestion(
    user_id: str,
    conversation_id: str,
    action: str,
    edited_text: str | None,
    port: MarketplacePort,
) -> dict[str, Any]:
    """Resumes interrupted conversation graph with human approval decision."""
    thread_id = f"conv:{user_id}:{conversation_id}"
    deps = NodeDeps(port=port)

    decision = {
        "action": action,
        "edited_text": edited_text,
    }
    res = await resume_conversation(
        thread_id=thread_id,
        decision=decision,
        deps=deps,
    )
    return res
