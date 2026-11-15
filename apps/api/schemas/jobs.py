"""Schemas for jobs and inbox management."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    description: str = ""
    client_name: str = ""
    client_id: str | None = None
    client_country: str | None = None
    category: str = "ai_ml"
    budget: float | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    budget_type: str = "fixed"
    connects_cost: int = 4
    fit_score: float | None = None
    risk_score: float | None = None
    client_trust_score: float | None = None
    risk_badges: list[str] = Field(default_factory=list)
    recommended_action: str = "pending"
    quote: float | None = None
    status: str = "not_analysed"
    skip_reason: str | None = None
    is_scam: bool = False
    scam_reason: str | None = None
    created_at: str | None = None
    posted_at: str | None = None


class JobDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    budget: float | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    budget_type: str = "fixed"
    connects_cost: int = 4
    client_name: str = ""
    client_id: str | None = None
    client_country: str | None = None
    category: str = "ai_ml"
    status: str = "not_analysed"
    posted_at: str | None = None
    risk_report: dict[str, Any] = Field(default_factory=dict)
    requirement_evidence_matrix: list[dict[str, Any]] = Field(default_factory=list)
    price_rationale: dict[str, Any] = Field(default_factory=dict)
    decision_reasoning: str | dict[str, Any] = ""
    last_run: dict[str, Any] | None = None


class SkipJobRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reason: str = Field(..., description="Mandatory reason for skipping this job opportunity.")
