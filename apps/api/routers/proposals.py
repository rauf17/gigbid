"""Router for proposal pipeline status and outcome columns."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from agent.marketplace_port import MarketplacePort
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.auth import UserResponse
from apps.api.schemas.proposals import ProposalPipelineResponse
from apps.api.services.proposals_service import get_proposal_pipeline

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("", response_model=ProposalPipelineResponse, operation_id="get_proposal_pipeline_stages")
async def get_proposals(
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> ProposalPipelineResponse:
    """Returns proposal cards categorized into lifecycle columns: drafted, submitted, viewed, replied, hired, lost."""
    return await get_proposal_pipeline(user_id=user.id, port=port)
