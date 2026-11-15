"""Router for analytics: category outcomes, connects expenditures, and LLM call cost."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.auth.deps import current_user
from apps.api.schemas.analytics import AnalyticsResponse
from apps.api.schemas.auth import UserResponse
from apps.api.services.analytics_service import get_analytics_report

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse, operation_id="get_analytics_summary")
async def get_analytics(
    user: Annotated[UserResponse, Depends(current_user)],
) -> AnalyticsResponse:
    """Returns analytics report: reply/hire rates, connects spent vs outcomes, LLM costs, and top rejection reasons."""
    return await get_analytics_report(user_id=user.id)
