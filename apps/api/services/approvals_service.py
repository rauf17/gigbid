"""Service layer for human review, draft inspection, and approval resumption."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status

from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_port import MarketplacePort
from agent.nodes.base import NodeDeps
from agent.runtime import get_checkpointer_and_store, pending_approvals, resume
from agent.state import BidStatus
from apps.api.schemas.approvals import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalDetailResponse,
    PendingApprovalItem,
)

logger = logging.getLogger(__name__)


async def list_pending_approvals(user_id: str) -> list[PendingApprovalItem]:
    """Retrieves all threads awaiting review for the current user."""
    items = await pending_approvals(user_id=user_id)
    return [
        PendingApprovalItem(
            thread_id=it["thread_id"],
            checkpoint_id=it.get("checkpoint_id"),
            created_at=str(it.get("created_at")) if it.get("created_at") else None,
            payload=it.get("payload") or {},
        )
        for it in items
    ]


async def get_approval_detail(user_id: str, thread_id: str) -> ApprovalDetailResponse:
    if not thread_id.startswith(f"{user_id}:"):
        thread_id = f"{user_id}:{thread_id}"

    config = {"configurable": {"thread_id": thread_id}}
    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st)
        snap = await graph.aget_state(config)
        if not snap or not snap.values:
            raise HTTPException(status_code=404, detail="No approval payload found for this thread")

        # Extract payload from interrupt or state values
        interrupt_payload: dict[str, Any] = {}
        if snap.tasks and snap.tasks[0].interrupts:
            interrupt_payload = snap.tasks[0].interrupts[0].value or {}

        values = dict(snap.values)
        draft = interrupt_payload.get("draft") or values.get("draft") or values.get("proposal_draft") or {}
        claim_ev = (
            interrupt_payload.get("claim_evidence")
            or interrupt_payload.get("claims_matrix")
            or values.get("claim_evidence")
            or []
        )
        risk = interrupt_payload.get("risk") or interrupt_payload.get("risk_report") or values.get("risk_report") or {}
        price = interrupt_payload.get("price_rationale") or values.get("price_rationale") or values.get("quote") or {}
        dry_run = interrupt_payload.get("dry_run") or interrupt_payload.get("dry_run_preview") or values.get("dry_run_preview") or {}
        critic = interrupt_payload.get("critic_comments") or values.get("critic_comments")
        compliance = interrupt_payload.get("compliance_comments") or values.get("compliance_comments")
        checkpoint_id = snap.config.get("configurable", {}).get("checkpoint_id")

        # Evidence store
        evidence_store = interrupt_payload.get("evidence_store") or {}
        if not evidence_store and values.get("evidence"):
            for ev in values["evidence"]:
                ev_id = getattr(ev, "id", None) or (ev.get("id") if isinstance(ev, dict) else "")
                if ev_id:
                    evidence_store[ev_id] = ev.model_dump() if hasattr(ev, "model_dump") else ev

        # Extract job metadata
        job_obj = interrupt_payload.get("job") or values.get("job") or {}
        job_id = interrupt_payload.get("job_id") or getattr(job_obj, "id", None) or (job_obj.get("id") if isinstance(job_obj, dict) else "")
        job_title = interrupt_payload.get("job_title") or getattr(job_obj, "title", None) or (job_obj.get("title") if isinstance(job_obj, dict) else "")

        return ApprovalDetailResponse(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            job_id=job_id,
            job_title=job_title,
            draft=draft,
            claim_evidence=claim_ev,
            evidence_store=evidence_store,
            risk=risk,
            price_rationale=price,
            dry_run=dry_run,
            critic_comments=critic,
            compliance_comments=compliance,
        )


async def decide_approval(
    user_id: str,
    thread_id: str,
    req: ApprovalDecisionRequest,
    port: MarketplacePort,
) -> ApprovalDecisionResponse:
    if not thread_id.startswith(f"{user_id}:"):
        thread_id = f"{user_id}:{thread_id}"

    deps = NodeDeps(port=port)
    decision: dict[str, Any] = {"action": req.action}

    if req.action == "reject":
        if not req.reason or not req.reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection requires an explicit reason",
            )
        decision["reason"] = req.reason.strip()

    elif req.action == "edit":
        if not req.edited_text or not req.edited_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Edited proposal text cannot be empty",
            )
        decision["edited_text"] = req.edited_text.strip()

    res = await resume(thread_id=thread_id, decision=decision, deps=deps)

    # Check if re-run compliance blocked the proposal edit
    violations: list[str] = []
    if req.action == "edit":
        compliance_check = res.get("compliance") or {}
        if isinstance(compliance_check, dict):
            violations = compliance_check.get("violations", [])

    final_status = res.get("status", BidStatus.SUBMITTED)
    if violations:
        return ApprovalDecisionResponse(
            thread_id=thread_id,
            status="blocked",
            action_taken=req.action,
            violations=violations,
            message="Edited proposal was blocked by compliance rules",
        )

    return ApprovalDecisionResponse(
        thread_id=thread_id,
        status=str(final_status),
        action_taken=req.action,
        violations=[],
        message=f"Action '{req.action}' recorded; bid graph execution resumed",
    )
