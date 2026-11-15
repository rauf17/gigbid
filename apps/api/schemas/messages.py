"""Schemas for client conversations and messaging."""
from __future__ import annotations

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


class SuggestedReplyResponse(BaseModel):
    detail: str = "Conversation graph not implemented yet"
    suggested_replies: list[str] = Field(default_factory=list)
