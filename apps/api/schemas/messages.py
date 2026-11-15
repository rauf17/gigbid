"""Schemas for client conversations, suggested replies, and message approvals."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    conversation_id: str
    sender_id: str
    sender_role: str
    text: str
    timestamp: str | None = None


class MessageReplyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(..., description="Reply text content.")


class SuggestedSlotItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    slot_id: str
    start_time: str
    end_time: str
    duration_min: int = 30
    formatted: str


class SuggestedReplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: str = ""
    thread_id: str = ""
    status: str = "awaiting_approval"
    intent: str = "question"
    suggested_reply: str | None = None
    suggested_replies: list[str] = Field(default_factory=list)
    proposed_slots: list[SuggestedSlotItem] = Field(default_factory=list)
    is_awaiting_approval: bool = True
    compliance_passed: bool = True
    risk_flags: list[str] = Field(default_factory=list)
    detail: str = "Suggested reply generated."


class ConversationApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["approve", "edit", "reject"] = Field(
        default="approve",
        description="Review decision ('approve', 'edit', 'reject').",
    )
    edited_text: str | None = Field(default=None, description="Edited reply text if action is 'edit'.")
    selected_slot_id: str | None = Field(default=None, description="Optional chosen slot ID.")
    reason: str | None = Field(default=None, description="Optional justification.")
