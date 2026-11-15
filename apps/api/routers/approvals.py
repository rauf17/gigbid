"""Router for pending approval inspection and human-in-the-loop decisions."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from agent.marketplace_port import MarketplacePort
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.approvals import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalDetailResponse,
    PendingApprovalItem,
)
from apps.api.schemas.auth import UserResponse
from apps.api.services.approvals_service import (
    decide_approval,
    get_approval_detail,
    list_pending_approvals,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[PendingApprovalItem], operation_id="list_pending_approvals_inbox")
async def get_approvals(
    user: Annotated[UserResponse, Depends(current_user)],
) -> list[PendingApprovalItem]:
    """Lists all threads awaiting human review for this user. Survives app restarts."""
    return await list_pending_approvals(user_id=user.id)


@router.get("/{thread_id}", response_model=ApprovalDetailResponse, operation_id="get_approval_payload")
async def get_approval(
    thread_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
) -> ApprovalDetailResponse:
    """Returns the full approval dossier: proposal draft, claim-evidence mapping, risk, and price rationale."""
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    return await get_approval_detail(user_id=user.id, thread_id=actual_thread_id)


@router.post("/{thread_id}", response_model=ApprovalDecisionResponse, operation_id="submit_approval_decision")
async def post_approval_decision(
    thread_id: str,
    req: ApprovalDecisionRequest,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> ApprovalDecisionResponse:
    """Submits human decision (approve, edit, reject) and resumes graph execution.

    - Reject requires an explicit reason.
    - Edit re-runs compliance verification.
    """
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    return await decide_approval(user_id=user.id, thread_id=actual_thread_id, req=req, port=port)
