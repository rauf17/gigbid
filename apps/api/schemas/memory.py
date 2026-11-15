"""Schemas for long-term memory inspection and deletion."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    namespace: list[str] = Field(default_factory=list)
    key: str
    value: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class MemoryListResponse(BaseModel):
    items: list[MemoryItemResponse] = Field(default_factory=list)
    count: int = 0
