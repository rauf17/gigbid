"""Typed Pydantic models for the internal MarketplacePort contract."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Job(BaseModel):
    """Internal domain model for a marketplace job posting."""
    id: str = Field(..., description="Unique job identifier.")
    title: str = Field(..., description="Job posting title.")
    description: str = Field(..., description="Job scope and description.")
    category: str = Field(..., description="Job category.")
    skills: list[str] = Field(default_factory=list, description="Tagged skill requirements.")
    budget_type: str = Field(..., description="Budget structure ('fixed' or 'hourly').")
    budget_min: float = Field(..., description="Minimum budget or hourly rate.")
    budget_max: float = Field(..., description="Maximum budget or hourly rate.")
    client_country: str = Field(..., description="Country of hiring client.")
    posted_at: str = Field(..., description="ISO 8601 posting timestamp.")
    connects_cost: int = Field(..., description="Connects required to submit proposal.")
    client_id: str | None = Field(default=None, description="Client identifier.")
    synthetic: bool = Field(default=True, description="Whether record is synthetic.")


class ClientHistory(BaseModel):
    """Internal domain model for client history and reputation metrics."""
    id: str = Field(..., description="Client identifier.")
    company: str = Field(..., description="Company name.")
    industry: str = Field(..., description="Industry sector.")
    country: str = Field(..., description="Client country.")
    payment_verified: bool = Field(..., description="Payment verification status.")
    total_spent: float = Field(..., description="Lifetime spend in USD.")
    hire_rate: float = Field(..., description="Hire rate between 0.0 and 1.0.")
    avg_rating: float = Field(..., description="Average client rating.")
    jobs_posted: int = Field(..., description="Total posted jobs.")
    review_count: int = Field(..., description="Total completed reviews.")


class ConnectsBalance(BaseModel):
    """Internal domain model for Connects balance."""
    balance: int = Field(..., description="Available Connects balance.")
    currency: str = Field(default="Connects", description="Currency unit.")


class Message(BaseModel):
    """Internal domain model for conversation messages."""
    id: str = Field(..., description="Message identifier.")
    conversation_id: str = Field(..., description="Conversation thread identifier.")
    sender: str = Field(..., description="Sender identity ('freelancer' or 'client').")
    text: str = Field(..., description="Message body text.")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    dry_run: bool = Field(default=False, description="Whether message was previewed only.")


class ProposalDraft(BaseModel):
    """Internal domain model for a saved or previewed proposal draft."""
    id: str = Field(..., description="Draft identifier.")
    job_id: str = Field(..., description="Target job identifier.")
    cover_letter: str = Field(..., description="Cover letter text.")
    screening_answers: list[dict[str, Any]] | dict[str, Any] | None = Field(
        default=None, description="Answers to client questions."
    )
    bid_amount: float = Field(..., description="Bid amount in USD.")
    connects_cost: int = Field(..., description="Connects required.")
    status: str = Field(..., description="Proposal status (e.g. 'draft').")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    dry_run: bool = Field(default=False, description="Whether draft was previewed only.")
    message: str = Field(..., description="Status explanation.")


class ProposalSubmit(BaseModel):
    """Internal domain model for a submitted proposal outcome."""
    id: str = Field(..., description="Proposal identifier.")
    job_id: str = Field(..., description="Target job identifier.")
    status: str = Field(..., description="Status ('submitted').")
    connects_cost: int = Field(..., description="Connects deducted.")
    connects_balance: int = Field(..., description="Remaining balance.")
    submitted_at: str | None = Field(default=None, description="Submission timestamp.")
    message: str = Field(..., description="Outcome message.")
    dry_run: bool = Field(default=False, description="Whether submission was previewed only.")
