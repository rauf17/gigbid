"""Pydantic schemas for authentication and tenant profiles."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(..., description="User email address.")
    password: str = Field(..., min_length=6, description="Password (min 6 characters).")
    persona_id: str = Field("ai_ml", description="Associated freelancer persona ID.")


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    persona_id: str
    created_at: str | None = None


class ProfileResponse(BaseModel):
    user_id: str
    persona_id: str
    hourly_rate: float = 50.0
    floor_rate: float = 30.0
    filters: dict[str, Any] = Field(default_factory=dict)
    weekly_connects_budget: int = 40
    autonomy_level: str = "semi_autonomous"
    saved_searches: list[dict[str, Any]] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    persona_id: str | None = None
    hourly_rate: float | None = None
    floor_rate: float | None = None
    filters: dict[str, Any] | None = None
    weekly_connects_budget: int | None = None
    autonomy_level: str | None = None
    saved_searches: list[dict[str, Any]] | None = None


class MarketplaceConnectRequest(BaseModel):
    token: str = Field(..., description="GigSim / Marketplace API token.")


class MessageResponse(BaseModel):
    status: str = "ok"
    message: str = ""
