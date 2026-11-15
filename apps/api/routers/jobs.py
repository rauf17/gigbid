"""Router for candidate job discovery, triage listing, and skipping."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from agent.marketplace_port import MarketplacePort
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.auth import MessageResponse, UserResponse
from apps.api.schemas.jobs import JobDetailResponse, JobSummaryResponse, SkipJobRequest
from apps.api.services.jobs_service import get_job_detail, list_jobs, record_job_skip

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobSummaryResponse], operation_id="list_jobs_inbox")
async def get_jobs_inbox(
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
    category: str | None = Query(None, description="Category filter (e.g. ai_ml, fullstack, data_analyst)"),
    min_fit: float | None = Query(None, description="Minimum fit score filter (0.0 to 1.0)"),
    status: str | None = Query(None, description="Job status filter (new, triaged, skipped)"),
    limit: int = Query(20, ge=1, le=100, description="Max jobs to return"),
) -> list[JobSummaryResponse]:
    """Retrieves candidate inbox jobs joined with offline triage results, sorted by fit score."""
    return await list_jobs(
        user_id=user.id,
        port=port,
        category=category,
        min_fit=min_fit,
        status_filter=status,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobDetailResponse, operation_id="get_job_details")
async def get_job_by_id(
    job_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> JobDetailResponse:
    """Retrieves full job spec, risk breakdown, requirements-to-evidence matrix, and pricing rationale."""
    return await get_job_detail(user_id=user.id, job_id=job_id, port=port)


@router.post("/{job_id}/skip", response_model=MessageResponse, operation_id="skip_job_candidate")
async def skip_job(
    job_id: str,
    req: SkipJobRequest,
    user: Annotated[UserResponse, Depends(current_user)],
) -> MessageResponse:
    """Marks a candidate job as skipped with a documented human rationale."""
    record_job_skip(user_id=user.id, job_id=job_id, reason=req.reason)
    return MessageResponse(status="skipped", message=f"Job {job_id} marked as skipped")
