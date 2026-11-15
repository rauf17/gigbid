"""FastAPI dependencies for authentication and tenant isolation."""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Header, HTTPException, status

from apps.api.auth.security import decode_access_token
from apps.api.auth.service import get_user_by_id
from apps.api.schemas.auth import UserResponse


async def current_user(
    authorization: Annotated[str | None, Header(description="Bearer token")] = None,
    access_token: Annotated[str | None, Cookie(description="HTTP-only session cookie")] = None,
) -> UserResponse:
    """Reusable dependency providing the authenticated tenant (UserResponse).

    Scopes all downstream queries and graph threads by user_id.
    """
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user_record = get_user_by_id(user_id)
    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse(
        id=user_record["id"],
        email=user_record["email"],
        persona_id=user_record.get("persona_id", "ai_ml"),
        created_at=user_record.get("created_at"),
    )
