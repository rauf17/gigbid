"""Router for liveness and external dependency health probes."""
from __future__ import annotations

from fastapi import APIRouter

from apps.api.schemas.health import HealthDependenciesResponse, HealthResponse
from apps.api.services.health_service import probe_dependencies

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="get_health_liveness")
async def get_health() -> HealthResponse:
    """Liveness probe returning basic API service status."""
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/health/dependencies", response_model=HealthDependenciesResponse, operation_id="get_dependencies_health")
async def get_dependencies() -> HealthDependenciesResponse:
    """Probes status of Postgres, Redis, Marketplace MCP, Portfolio MCP, and LLM configuration."""
    return await probe_dependencies()
