"""Pydantic Models and Data Schemas for GigSim (AI-4016 GigBid Phase 1b Part 3).

Defines public request and response schemas. Hidden fields and evaluation labels
are strictly omitted from all public schemas.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    simulated_time: str
    released_jobs_count: int
    connects_balance: int
    active_proposals_count: int


class JobPublic(BaseModel):
    id: str
    title: str
    description: str
    category: str
    skills: list[str]
    budget_type: str
    budget_min: float
    budget_max: float
    client_country: str
    client_id: str
    posted_at: str
    connects_cost: int
    synthetic: bool


class JobListResponse(BaseModel):
    items: list[JobPublic]
    next_cursor: str | None = None
    total: int


class ConnectsBalanceResponse(BaseModel):
    balance: int
    currency: str = "connects"
    weekly_grant: int
    last_grant_date: str


class ProposalCreateRequest(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: Any = None
    bid_amount: float = Field(gt=0)
    dry_run: bool = False


class ProposalResponse(BaseModel):
    id: str
    job_id: str
    cover_letter: str
    screening_answers: Any = None
    bid_amount: float
    connects_cost: int
    status: str
    created_at: str
    submitted_at: str | None = None
    dry_run: bool = False
    message: str | None = None


class ProposalSubmitResponse(BaseModel):
    id: str
    job_id: str
    status: str
    connects_cost: int
    connects_balance: int
    submitted_at: str
    message: str


class MessageCreateRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender: str  # "freelancer" or "client"
    text: str
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    proposal_id: str
    job_id: str
    client_id: str
    created_at: str
    updated_at: str
    latest_message: str | None = None


class TickResponse(BaseModel):
    released_jobs: int
    total_released: int
    advanced_time: str
    proposals_evaluated: int
    status_updates: list[dict[str, Any]]


class ResetResponse(BaseModel):
    status: str = "reset"
    message: str
