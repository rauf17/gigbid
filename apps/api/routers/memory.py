"""Router for inspecting and managing agent long-term memory."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from apps.api.auth.deps import current_user
from apps.api.schemas.auth import MessageResponse, UserResponse
from apps.api.schemas.memory import MemoryListResponse
from apps.api.services.memory_service import delete_memory_key, get_user_memory

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse, operation_id="list_user_memory_items")
async def list_memory_items(
    user: Annotated[UserResponse, Depends(current_user)],
    namespace: str | None = Query(None, description="Optional namespace filter ('style' or 'outcome')"),
) -> MemoryListResponse:
    """Lists long-term memory entries for the authenticated user."""
    return await get_user_memory(user_id=user.id, namespace=namespace)


@router.delete("/{item_id}", response_model=MessageResponse, operation_id="delete_user_memory_item")
async def delete_memory_item_route(
    item_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
    namespace: str = Query("style", description="Target namespace ('style' or 'outcome')"),
) -> MessageResponse:
    """Deletes an item from the user's long-term memory store."""
    return await delete_memory_key(user_id=user.id, item_id=item_id, namespace=namespace)
