"""Pydantic schemas and models for Workspace MCP Server."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TimeSlot(BaseModel):
    """Available calendar meeting slot."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    slot_id: str = Field(..., description="Unique deterministic slot identifier.")
    start_time: str = Field(..., description="ISO 8601 start timestamp in UTC.")
    end_time: str = Field(..., description="ISO 8601 end timestamp in UTC.")
    duration_min: int = Field(default=30, description="Duration of slot in minutes.")
    formatted: str = Field(..., description="Human-readable representation, e.g. 'Tomorrow, 2:00 PM - 2:30 PM UTC'.")


class ListFreeSlotsInput(BaseModel):
    """Input parameters for listing available free slots."""
    model_config = ConfigDict(extra="forbid")

    days_ahead: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Number of business days ahead to search for meeting availability (1-14 days).",
    )
    duration_min: int = Field(
        default=30,
        ge=15,
        le=120,
        description="Meeting slot duration in minutes (15-120 min).",
    )


class ListFreeSlotsOutput(BaseModel):
    """Output envelope for free slots listing."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    slots: list[TimeSlot] = Field(default_factory=list, description="List of free calendar slots.")
    count: int = Field(default=0, description="Number of available slots found.")
    timezone: str = Field(default="UTC", description="Calendar reference timezone.")


class CreateTentativeHoldInput(BaseModel):
    """Input parameters for creating a tentative calendar hold."""
    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Identifier of the free slot to tentatively hold.",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Title or client context for the interview hold.",
    )
    idempotency_key: str = Field(
        default="",
        max_length=128,
        description="Client idempotency key for safe retries without duplicate holds.",
    )


class TentativeHoldOutput(BaseModel):
    """Output envelope for a tentative calendar hold."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    hold_id: str = Field(..., description="Unique identifier for the created hold.")
    slot_id: str = Field(..., description="Held calendar slot ID.")
    title: str = Field(..., description="Hold title.")
    start_time: str = Field(..., description="Start timestamp in UTC.")
    end_time: str = Field(..., description="End timestamp in UTC.")
    status: str = Field(default="tentative", description="Hold status ('tentative' or 'confirmed').")
    held_at: str = Field(..., description="Timestamp when hold was registered.")
    idempotency_key: str | None = Field(default=None, description="Idempotency key.")


class CreateEmailDraftInput(BaseModel):
    """Input parameters for creating an email draft."""
    model_config = ConfigDict(extra="forbid")

    to: str = Field(
        ...,
        min_length=3,
        max_length=254,
        description="Recipient email address.",
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Email subject line.",
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Full text body of the email draft.",
    )
    idempotency_key: str = Field(
        default="",
        max_length=128,
        description="Client idempotency key for safe draft creation.",
    )


class EmailDraftOutput(BaseModel):
    """Output envelope for an email draft."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    draft_id: str = Field(..., description="Unique draft identifier.")
    to: str = Field(..., description="Recipient email address.")
    subject: str = Field(..., description="Subject line.")
    body: str = Field(..., description="Draft body.")
    status: str = Field(default="draft", description="Status ('draft').")
    created_at: str = Field(..., description="Creation timestamp in UTC.")
    idempotency_key: str | None = Field(default=None, description="Idempotency key.")


class WorkspaceErrorOutput(BaseModel):
    """Standard error response."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    error: str
    detail: str
    code: int = 400
