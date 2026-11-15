"""Schemas for human-in-the-loop approvals."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PendingApprovalItem(BaseModel):
    thread_id: str
    checkpoint_id: str | None = None
    created_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalDetailResponse(BaseModel):
    thread_id: str
    checkpoint_id: str | None = None
    job_id: str = ""
    job_title: str = ""
    draft: dict[str, Any] = Field(default_factory=dict)
    claim_evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_store: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    price_rationale: dict[str, Any] = Field(default_factory=dict)
    dry_run: dict[str, Any] = Field(default_factory=dict)
    critic_comments: dict[str, Any] | None = None
    compliance_comments: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["approve", "edit", "reject"] = Field(..., description="Action decision for approval gate.")
    edited_text: str | None = Field(None, description="Updated proposal text if action is 'edit'.")
    reason: str | None = Field(None, description="Mandatory explanation if action is 'reject'.")


class ApprovalDecisionResponse(BaseModel):
    thread_id: str
    status: str
    action_taken: str
    violations: list[str] = Field(default_factory=list)
    message: str = ""
