"""Global API dependencies: marketplace port and checkpointer/store helpers."""
from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status

from agent.marketplace_port import (
    MarketplacePort,
    MarketplaceUnavailable,
    McpMarketplacePort,
)
from apps.api.auth.deps import current_user
from apps.api.auth.service import get_marketplace_token
from apps.api.schemas.auth import UserResponse

logger = logging.getLogger(__name__)


def get_marketplace_port(user: Annotated[UserResponse, Depends(current_user)]) -> MarketplacePort:
    """Dependency returning the active MarketplacePort instance scoped to current user.

    Can be overridden in tests via app.dependency_overrides[get_marketplace_port].
    """
    token = get_marketplace_token(user.id)
    return McpMarketplacePort(user_id=user.id, token=token)


def handle_marketplace_error(exc: Exception, queued: bool = False) -> None:
    """Translates marketplace port failures into structured 503 degraded responses."""
    if isinstance(exc, (MarketplaceUnavailable, httpx.ConnectError, httpx.ConnectTimeout)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "marketplace_unavailable", "retryable": True, "queued": queued},
        )
    raise exc
