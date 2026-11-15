"""Service layer for marketplace conversation threads and messaging."""
from __future__ import annotations

import logging

import httpx

from agent.marketplace_port import MarketplacePort, MarketplacePortError
from apps.api.deps import handle_marketplace_error
from apps.api.schemas.messages import MessageItem

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
