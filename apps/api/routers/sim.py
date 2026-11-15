"""Development-only simulator controls for advancing GigSim world state."""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, status

from apps.api.schemas.auth import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sim", tags=["simulation"])


@router.post("/tick", response_model=MessageResponse, operation_id="trigger_simulator_tick")
async def trigger_sim_tick() -> MessageResponse:
    """Advances GigSim simulation clock by one tick. Disabled in production environments."""
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulator control is disabled in production",
        )

    gigsim_url = os.getenv("GIGSIM_BASE_URL", "http://localhost:8081").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{gigsim_url}/admin/tick")
            if resp.status_code == 200:
                data = resp.json()
                return MessageResponse(
                    status="ok",
                    message=f"Simulation advanced to tick {data.get('tick', 'unknown')}",
                )
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GigSim tick failed: {resp.text}",
            )
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "gigsim_unreachable", "message": str(exc)},
        ) from exc
