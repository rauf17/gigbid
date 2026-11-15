"""Schemas for system health and external dependency checks."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class DependencyStatus(BaseModel):
    name: str
    status: str  # ok, unreachable, error, not_configured
    details: str | None = None


class HealthDependenciesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str  # ok, degraded, unhealthy
    dependencies: dict[str, DependencyStatus] = Field(default_factory=dict)
