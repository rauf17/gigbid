"""Router for client conversations, suggested replies, and message approvals."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from agent.marketplace_port import MarketplacePort
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.auth import UserResponse
from apps.api.schemas.messages import (
    ConversationApprovalRequest,
    MessageItem,
    MessageReplyRequest,
    SuggestedReplyResponse,
)
from apps.api.services.messages_service import (
    approve_conversation_suggestion,
    get_conversation_messages,
    get_or_create_conversation_suggestion,
    send_conversation_reply,
)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageItem], operation_id="list_conversation_messages")
async def list_messages(
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
    conversation_id: str = Query("conv_default", description="Active conversation thread ID"),
) -> list[MessageItem]:
    """Retrieves message history for a conversation thread from marketplace port."""
    return await get_conversation_messages(conversation_id=conversation_id, port=port)


@router.post("/{conversation_id}/reply", response_model=MessageItem, operation_id="send_conversation_reply_msg")
async def reply_message(
    conversation_id: str,
    req: MessageReplyRequest,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> MessageItem:
    """Sends a freelancer reply message to the specified conversation thread."""
    return await send_conversation_reply(conversation_id=conversation_id, text=req.text, port=port)


@router.get(
    "/{conversation_id}/suggestion",
    response_model=SuggestedReplyResponse,
    operation_id="get_conversation_suggestion",
)
@router.get(
    "/{conversation_id}/suggest",
    response_model=SuggestedReplyResponse,
    operation_id="suggest_conversation_reply",
    include_in_schema=False,
)
async def suggest_reply(
    conversation_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> SuggestedReplyResponse:
    """Starts or resumes the conversation graph and returns suggested reply, intent, and slots."""
    return await get_or_create_conversation_suggestion(
        user_id=user.id,
        conversation_id=conversation_id,
        port=port,
        persona_id=user.persona_id,
    )


@router.post(
    "/{conversation_id}/approve",
    response_model=dict[str, Any],
    operation_id="approve_conversation_reply",
)
async def approve_reply(
    conversation_id: str,
    req: ConversationApprovalRequest,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> dict[str, Any]:
    """Resumes the conversation graph with approval decision, sends message and holds interview slot."""
    return await approve_conversation_suggestion(
        user_id=user.id,
        conversation_id=conversation_id,
        action=req.action,
        edited_text=req.edited_text,
        port=port,
    )
