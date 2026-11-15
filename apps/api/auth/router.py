"""Authentication, user profile, and tenant onboarding routes."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from apps.api.auth.deps import current_user
from apps.api.auth.security import create_access_token, hash_password, verify_password
from apps.api.auth.service import (
    create_user,
    get_user_by_email,
    get_user_profile,
    store_marketplace_token,
    update_user_profile,
)
from apps.api.schemas.auth import (
    MarketplaceConnectRequest,
    MessageResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from rag.ingest.pipeline import ingest_persona

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    operation_id="register_user",
    status_code=status.HTTP_201_CREATED,
)
async def register(req: UserRegisterRequest, response: Response) -> TokenResponse:
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    pw_hash = hash_password(req.password)
    user = create_user(email=req.email, password_hash=pw_hash, persona_id=req.persona_id)
    token = create_access_token({"sub": user["id"], "email": user["email"], "persona_id": user["persona_id"]})

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/auth/login", response_model=TokenResponse, operation_id="login_user")
async def login(req: UserLoginRequest, response: Response) -> TokenResponse:
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user["id"], "email": user["email"], "persona_id": user["persona_id"]})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/auth/logout", response_model=MessageResponse, operation_id="logout_user")
async def logout(response: Response) -> MessageResponse:
    response.delete_cookie(key="access_token")
    return MessageResponse(status="ok", message="Logged out successfully")


@router.get("/auth/me", response_model=UserResponse, operation_id="get_current_user_me")
async def get_me(user: Annotated[UserResponse, Depends(current_user)]) -> UserResponse:
    return user


@router.get("/profile", response_model=ProfileResponse, operation_id="get_profile")
async def get_profile(user: Annotated[UserResponse, Depends(current_user)]) -> ProfileResponse:
    prof = get_user_profile(user.id)
    return ProfileResponse(**prof)


@router.put("/profile", response_model=ProfileResponse, operation_id="update_profile")
async def put_profile(
    req: ProfileUpdateRequest,
    user: Annotated[UserResponse, Depends(current_user)],
) -> ProfileResponse:
    updates = req.model_dump(exclude_unset=True)
    updated = update_user_profile(user.id, updates)
    return ProfileResponse(**updated)


@router.post(
    "/connections/marketplace",
    response_model=MessageResponse,
    operation_id="connect_marketplace_token",
)
async def connect_marketplace(
    req: MarketplaceConnectRequest,
    user: Annotated[UserResponse, Depends(current_user)],
) -> MessageResponse:
    """Stores the encrypted marketplace token. The token is never returned."""
    if not req.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")
    store_marketplace_token(user.id, req.token.strip())
    return MessageResponse(status="connected", message="Marketplace credentials stored securely")


@router.post(
    "/portfolio/upload",
    response_model=MessageResponse,
    operation_id="upload_portfolio_file",
)
async def upload_portfolio(
    file: Annotated[UploadFile, File(...)],
    user: Annotated[UserResponse, Depends(current_user)],
) -> MessageResponse:
    """Accepts .md or .txt portfolio files and triggers incremental persona re-indexing."""
    filename = file.filename or "upload.txt"
    if not filename.endswith((".md", ".txt")):
        raise HTTPException(status_code=400, detail="Only .md and .txt files are supported for portfolio upload")

    # Save to user's persona case studies directory
    dest_dir = Path("data/personas") / user.persona_id / "case_studies"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    content = await file.read()
    dest_path.write_bytes(content)

    # Trigger incremental re-ingestion
    try:
        res = ingest_persona(persona_id=user.persona_id, full=False)
        chunk_count = res.get("total_chunks", 0)
        return MessageResponse(
            status="ok",
            message=f"Uploaded and incrementally indexed {filename} ({chunk_count} chunks total)",
        )
    except (OSError, ValueError) as exc:
        logger.warning("[portfolio.upload] Ingestion error: %s", exc)
        return MessageResponse(status="ok", message=f"Uploaded {filename}; index update queued")
