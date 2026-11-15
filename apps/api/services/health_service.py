"""Service layer for health checks and external dependency probes."""
from __future__ import annotations

import logging
import os

import httpx
import psycopg
import redis.asyncio as aioredis

from agent.db import get_db_url
from apps.api.schemas.health import DependencyStatus, HealthDependenciesResponse

logger = logging.getLogger(__name__)


async def probe_dependencies() -> HealthDependenciesResponse:
    deps: dict[str, DependencyStatus] = {}

    # 1. Postgres probe
    try:
        url = get_db_url()
        with psycopg.connect(url, connect_timeout=1) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            deps["postgres"] = DependencyStatus(name="postgres", status="ok", details="Connected")
    except Exception as exc:  # noqa: BLE001
        deps["postgres"] = DependencyStatus(name="postgres", status="error", details=str(exc))

    # 2. Redis probe
    try:
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
        client = aioredis.from_url(redis_url, socket_timeout=1.0)
        await client.ping()
        await client.aclose()
        deps["redis"] = DependencyStatus(name="redis", status="ok", details="Connected")
    except Exception as exc:  # noqa: BLE001
        deps["redis"] = DependencyStatus(name="redis", status="error", details=str(exc))

    # 3. Marketplace MCP probe
    mcp_url = os.getenv("MARKETPLACE_MCP_URL", "http://localhost:8002/mcp")
    base_mcp = mcp_url.replace("/mcp", "")
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{base_mcp}/health")
            if resp.status_code in {200, 401, 404, 405}:
                deps["marketplace_mcp"] = DependencyStatus(name="marketplace_mcp", status="ok", details="Reachable")
            else:
                deps["marketplace_mcp"] = DependencyStatus(
                    name="marketplace_mcp",
                    status="unreachable",
                    details=f"HTTP {resp.status_code}",
                )
    except Exception as exc:  # noqa: BLE001
        deps["marketplace_mcp"] = DependencyStatus(name="marketplace_mcp", status="unreachable", details=str(exc))

    # 4. Portfolio MCP probe
    port_mcp_url = os.getenv("PORTFOLIO_MCP_URL", "http://localhost:8001/mcp")
    base_port_mcp = port_mcp_url.replace("/mcp", "")
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{base_port_mcp}/health")
            if resp.status_code in {200, 404, 405}:
                deps["portfolio_mcp"] = DependencyStatus(name="portfolio_mcp", status="ok", details="Reachable")
            else:
                deps["portfolio_mcp"] = DependencyStatus(
                    name="portfolio_mcp",
                    status="unreachable",
                    details=f"HTTP {resp.status_code}",
                )
    except Exception as exc:  # noqa: BLE001
        deps["portfolio_mcp"] = DependencyStatus(name="portfolio_mcp", status="unreachable", details=str(exc))

    # 5. LLM Provider key probe
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if groq_key or openai_key:
        deps["llm_provider"] = DependencyStatus(name="llm_provider", status="ok", details="API key configured")
    else:
        deps["llm_provider"] = DependencyStatus(
            name="llm_provider",
            status="not_configured",
            details="Missing GROQ_API_KEY or OPENAI_API_KEY",
        )

    # Calculate overall status
    is_pg_ok = deps["postgres"].status == "ok"
    is_mcp_ok = deps["marketplace_mcp"].status == "ok"
    if is_pg_ok and is_mcp_ok:
        overall = "ok"
    elif is_pg_ok and not is_mcp_ok:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthDependenciesResponse(status=overall, dependencies=deps)
