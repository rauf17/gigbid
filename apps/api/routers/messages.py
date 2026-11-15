"""Router for client conversations and thin message forwarding."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent.marketplace_port import MarketplacePort
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.auth import UserResponse
from apps.api.schemas.messages import MessageItem, MessageReplyRequest, SuggestedReplyResponse
from apps.api.services.messages_service import (
    get_conversation_messages,
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
    "/{conversation_id}/suggest",
    response_model=SuggestedReplyResponse,
    operation_id="suggest_conversation_reply",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def suggest_reply(
    conversation_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
) -> SuggestedReplyResponse:
    """Returns 501 Not Implemented: conversation agent graph is scheduled for subsequent release."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversation graph not implemented yet. Suggested replies will be available in Phase 5.",
    )
