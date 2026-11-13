"""Structured Pydantic input and output schemas for Marketplace MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Output Schemas
# ---------------------------------------------------------

class JobItem(BaseModel):
    """Cleaned public job representation."""
    id: str = Field(..., description="Unique job identifier.")
    title: str = Field(..., description="Job posting title.")
    description: str = Field(..., description="Job requirements and context.")
    category: str = Field(..., description="Job category (e.g. AI/ML, Full-Stack Web, Data Analysis).")
    skills: list[str] = Field(default_factory=list, description="Tagged skill requirements.")
    budget_type: str = Field(..., description="Budget structure: 'fixed' or 'hourly'.")
    budget_min: float = Field(..., description="Minimum budget or hourly rate.")
    budget_max: float = Field(..., description="Maximum budget or hourly rate.")
    client_country: str = Field(..., description="Client country location.")
    posted_at: str = Field(..., description="ISO 8601 posting timestamp.")
    connects_cost: int = Field(..., description="Connects required to submit proposal.")
    client_id: str | None = Field(default=None, description="Hiring client identifier.")
    synthetic: bool = Field(default=True, description="Indicates synthetic test data.")


class SearchJobsOutput(BaseModel):
    """Output schema for search_jobs tool."""
    jobs: list[JobItem] = Field(default_factory=list, description="List of matched jobs.")
    total: int = Field(..., description="Total count of returned jobs.")


class ClientHistoryOutput(BaseModel):
    """Output schema for get_client_history tool."""
    id: str = Field(..., description="Client identifier.")
    company: str = Field(..., description="Client company or display name.")
    industry: str = Field(..., description="Client industry sector.")
    country: str = Field(..., description="Client country location.")
    payment_verified: bool = Field(..., description="Whether payment method is verified.")
    total_spent: float = Field(..., description="Total lifetime freelancer spend in USD.")
    hire_rate: float = Field(..., description="Hire rate between 0.0 and 1.0.")
    avg_rating: float = Field(..., description="Average client rating (1.0 to 5.0).")
    jobs_posted: int = Field(..., description="Total jobs posted by client.")
    review_count: int = Field(..., description="Number of completed freelancer reviews.")


class ConnectsBalanceOutput(BaseModel):
    """Output schema for get_connects_balance tool."""
    balance: int = Field(..., description="Current available Connects balance.")
    currency: str = Field(default="Connects", description="Currency unit.")


class MessageItem(BaseModel):
    """Individual conversation message."""
    id: str = Field(..., description="Unique message identifier.")
    conversation_id: str = Field(..., description="Conversation thread identifier.")
    sender: str = Field(..., description="Message sender ('freelancer' or 'client').")
    text: str = Field(..., description="Message text content.")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    dry_run: bool = Field(default=False, description="Whether message was a dry-run preview.")


class ListMessagesOutput(BaseModel):
    """Output schema for list_messages tool."""
    conversation_id: str = Field(..., description="Conversation thread identifier.")
    messages: list[MessageItem] = Field(default_factory=list, description="List of messages.")


class ProposalDraftOutput(BaseModel):
    """Output schema for create_proposal_draft tool."""
    id: str = Field(..., description="Proposal identifier.")
    job_id: str = Field(..., description="Target job identifier.")
    cover_letter: str = Field(..., description="Generated cover letter.")
    screening_answers: list[dict[str, Any]] | dict[str, Any] | None = Field(
        default=None, description="Answers to client screening questions."
    )
    bid_amount: float = Field(..., description="Bid amount in USD.")
    connects_cost: int = Field(..., description="Connects cost to submit.")
    status: str = Field(..., description="Proposal status (e.g. 'draft').")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    dry_run: bool = Field(default=False, description="Whether draft was created as a preview.")
    message: str = Field(..., description="Status explanation.")


class ProposalSubmitOutput(BaseModel):
    """Output schema for submit_proposal tool."""
    id: str = Field(..., description="Proposal identifier.")
    job_id: str = Field(..., description="Target job identifier.")
    status: str = Field(..., description="Proposal status ('submitted' or 'draft').")
    connects_cost: int = Field(..., description="Connects deducted.")
    connects_balance: int = Field(..., description="Remaining Connects balance.")
    submitted_at: str | None = Field(default=None, description="Submission timestamp.")
    message: str = Field(..., description="Submission outcome message.")
    dry_run: bool = Field(default=False, description="Whether submission was a dry-run preview.")


class ErrorOutput(BaseModel):
    """Structured error output schema returned in degraded or failure modes."""
    error: str = Field(..., description="Machine-readable error code.")
    retryable: bool = Field(..., description="Whether client may retry.")
    detail: str | None = Field(default=None, description="Optional diagnostic details.")
    retry_after: float | None = Field(default=None, description="Seconds to wait before retry.")
