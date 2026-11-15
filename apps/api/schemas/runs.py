"""Schemas for bid graph run execution, state tracking, and tracing."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_id: str = Field(..., description="ID of the job to process through the bid graph.")
    persona_id: str | None = Field(None, description="Optional persona override (defaults to user's persona).")


class RunCreateResponse(BaseModel):
    thread_id: str
    status: str = "running"
    message: str = "Bid graph execution started in background"


class RunStateResponse(BaseModel):
    thread_id: str
    status: str
    state_summary: dict[str, Any] = Field(default_factory=dict)
    current_node: str | None = None
    is_awaiting_approval: bool = False
    checkpoint_id: str | None = None


class TraceItem(BaseModel):
    id: int | None = None
    node_name: str
    tool_name: str | None = None
    observation: str | None = None
    tokens: int = 0
    duration_ms: float = 0.0
    created_at: str | None = None


class RunTraceResponse(BaseModel):
    thread_id: str
    trace_id: str | None = None
    trace_url: str | None = None
    traces: list[TraceItem] = Field(default_factory=list)


class ReplayRunRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    checkpoint_id: str = Field(..., description="Target historical checkpoint ID to re-execute from.")
