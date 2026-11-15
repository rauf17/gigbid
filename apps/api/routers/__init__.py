"""Routers package exports."""
from apps.api.routers.analytics import router as analytics_router
from apps.api.routers.approvals import router as approvals_router
from apps.api.routers.health import router as health_router
from apps.api.routers.jobs import router as jobs_router
from apps.api.routers.memory import router as memory_router
from apps.api.routers.messages import router as messages_router
from apps.api.routers.proposals import router as proposals_router
from apps.api.routers.runs import router as runs_router
from apps.api.routers.sim import router as sim_router

__all__ = [
    "analytics_router",
    "approvals_router",
    "health_router",
    "jobs_router",
    "memory_router",
    "messages_router",
    "proposals_router",
    "runs_router",
    "sim_router",
]
