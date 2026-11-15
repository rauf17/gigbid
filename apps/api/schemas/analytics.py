"""Schemas for analytics, outcomes, and LLM accounting."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategoryOutcomeItem(BaseModel):
    category: str
    bids: int = 0
    replies: int = 0
    hires: int = 0
    reply_rate: float = 0.0
    hire_rate: float = 0.0


class ConnectsUsageItem(BaseModel):
    category: str
    connects_spent: int = 0
    proposals_submitted: int = 0
    hires_won: int = 0


class CostLatencyItem(BaseModel):
    model: str
    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    outcomes_by_category: list[CategoryOutcomeItem] = Field(default_factory=list)
    connects_spent_vs_outcomes: list[ConnectsUsageItem] = Field(default_factory=list)
    cost_and_latency: list[CostLatencyItem] = Field(default_factory=list)
    top_rejection_reasons: list[dict[str, Any]] = Field(default_factory=list)
