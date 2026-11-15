"""Schemas for proposal lifecycle and pipeline status."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProposalItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    thread_id: str
    job_id: str
    persona_id: str
    status: str  # drafted, submitted, viewed, replied, interview, hired, lost
    bid_amount: float | None = None
    proposal_text: str | None = None
    created_at: str | None = None


class ProposalPipelineResponse(BaseModel):
    drafted: list[ProposalItem] = Field(default_factory=list)
    submitted: list[ProposalItem] = Field(default_factory=list)
    viewed: list[ProposalItem] = Field(default_factory=list)
    replied: list[ProposalItem] = Field(default_factory=list)
    interview: list[ProposalItem] = Field(default_factory=list)
    hired: list[ProposalItem] = Field(default_factory=list)
    lost: list[ProposalItem] = Field(default_factory=list)
