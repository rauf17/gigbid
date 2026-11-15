"""Service layer for inspecting and pruning agent long-term memory."""
from __future__ import annotations

import logging

from agent.memory.store import delete_memory_item, list_memory
from agent.runtime import get_checkpointer_and_store
from apps.api.schemas.auth import MessageResponse
from apps.api.schemas.memory import MemoryItemResponse, MemoryListResponse

logger = logging.getLogger(__name__)


async def get_user_memory(user_id: str, namespace: str | None = None) -> MemoryListResponse:
    async with get_checkpointer_and_store() as (_, st):
        raw_items = await list_memory(user_id=user_id, namespace=namespace, store=st)
        items = [
            MemoryItemResponse(
                namespace=list(it.namespace),
                key=it.key,
                value=it.value,
                created_at=it.created_at,
                updated_at=it.updated_at,
            )
            for it in raw_items
        ]
        return MemoryListResponse(items=items, count=len(items))


async def delete_memory_key(user_id: str, item_id: str, namespace: str = "style") -> MessageResponse:
    async with get_checkpointer_and_store() as (_, st):
        success = await delete_memory_item(user_id=user_id, namespace=namespace, key=item_id, store=st)
        if success:
            return MessageResponse(status="ok", message=f"Memory item '{item_id}' deleted")
        return MessageResponse(status="not_found", message=f"Memory item '{item_id}' was not found")
