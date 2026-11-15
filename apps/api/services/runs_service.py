"""Service layer for run lifecycle, state querying, tracing, and replay."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import BackgroundTasks, HTTPException, status

from agent.db import get_audit_traces
from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_port import MarketplacePort, MarketplaceUnavailable
from agent.nodes.base import NodeDeps
from agent.runtime import get_checkpointer_and_store, replay, run_job
from agent.state import BidStatus
from apps.api.schemas.runs import (
    ReplayRunRequest,
    RunCreateResponse,
    RunStateResponse,
    RunTraceResponse,
    TraceItem,
)

logger = logging.getLogger(__name__)


async def _execute_graph_background(
    job_dict: dict[str, Any],
    user_id: str,
    persona_id: str,
    port: MarketplacePort,
) -> None:
    try:
        deps = NodeDeps(port=port)
        await run_job(job=job_dict, user_id=user_id, persona_id=persona_id, deps=deps)
    except Exception as exc:  # noqa: BLE001
        logger.error("[runs_service] Background run_job failed for user %s: %s", user_id, exc)


async def _enqueue_to_arq_worker(user_id: str, job_id: str) -> bool:
    """Queues analysis job in Arq / Redis for offline retry."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
        settings = RedisSettings.from_dsn(redis_url)
        pool = await create_pool(settings)
        await pool.enqueue_job("analyse_job", user_id, job_id, _job_id=f"analyse:{user_id}:{job_id}")
        await pool.aclose()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("[runs_service] Failed enqueueing to Arq worker: %s", exc)
        return False


async def start_run(
    user_id: str,
    job_id: str,
    persona_id: str,
    port: MarketplacePort,
    background_tasks: BackgroundTasks,
) -> RunCreateResponse:
    thread_id = f"{user_id}:{job_id}"

    # Try fetching candidate job from marketplace
    try:
        job = await port.get_job(job_id)
        job_dict = job.model_dump()
    except (MarketplaceUnavailable, httpx.ConnectError, httpx.ConnectTimeout) as exc:
        logger.warning("[runs_service] Marketplace unavailable; queuing analysis work: %s", exc)
        queued = await _enqueue_to_arq_worker(user_id, job_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "marketplace_unavailable", "retryable": True, "queued": queued},
        ) from exc
    except Exception as exc:
        logger.error("[runs_service] get_job error: %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed retrieving job {job_id}: {exc}") from exc

    # Start graph execution in background task
    background_tasks.add_task(_execute_graph_background, job_dict, user_id, persona_id, port)
    return RunCreateResponse(thread_id=thread_id, status="running")


async def get_run_state(user_id: str, thread_id: str) -> RunStateResponse:
    if not thread_id.startswith(f"{user_id}:"):
        raise HTTPException(status_code=404, detail="Run thread not found or access denied")

    config = {"configurable": {"thread_id": thread_id}}
    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st)
        snap = await graph.aget_state(config)
        if not snap or not snap.values:
            raise HTTPException(status_code=404, detail="Run thread has not produced any state yet")

        values = dict(snap.values)
        raw_status = values.get("status", "unknown")

        is_awaiting = (
            raw_status == BidStatus.AWAITING_APPROVAL
            or "approval" in snap.next
            or any(t.interrupts for t in snap.tasks)
        )

        current_node = snap.next[0] if snap.next else None
        if raw_status == BidStatus.DEAD_LETTER:
            run_status = "dead_letter"
        elif raw_status == BidStatus.REJECTED or is_awaiting:
            run_status = "needs_attention" if is_awaiting else "rejected"
        else:
            run_status = str(raw_status)

        checkpoint_id = snap.config.get("configurable", {}).get("checkpoint_id")

        return RunStateResponse(
            thread_id=thread_id,
            status=run_status,
            state_summary={
                "job_id": values.get("job", {}).get("id") if isinstance(values.get("job"), dict) else None,
                "persona_id": values.get("persona_id"),
                "status": raw_status,
                "trace_id": values.get("trace_id"),
                "fit_score": values.get("fit_score"),
                "risk_score": values.get("risk_score"),
                "quote": values.get("quote"),
            },
            current_node=current_node,
            is_awaiting_approval=is_awaiting,
            checkpoint_id=checkpoint_id,
        )


async def get_run_trace(user_id: str, thread_id: str) -> RunTraceResponse:
    if not thread_id.startswith(f"{user_id}:"):
        raise HTTPException(status_code=404, detail="Run thread not found or access denied")

    traces_raw = get_audit_traces(thread_id)
    trace_items = [
        TraceItem(
            id=t.get("id"),
            node_name=t.get("node_name", ""),
            tool_name=t.get("tool_name"),
            observation=t.get("observation"),
            tokens=t.get("tokens", 0),
            duration_ms=t.get("duration_ms", 0.0),
            created_at=str(t.get("created_at")) if t.get("created_at") else None,
        )
        for t in traces_raw
    ]

    trace_id = traces_raw[0].get("trace_id") if traces_raw else None
    trace_url: str | None = None
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "gigbid")
    if os.getenv("LANGSMITH_API_KEY") and trace_id:
        trace_url = f"https://smith.langchain.com/o/default/projects/p/{langsmith_project}/r/{trace_id}"

    return RunTraceResponse(
        thread_id=thread_id,
        trace_id=trace_id,
        trace_url=trace_url,
        traces=trace_items,
    )


async def replay_run_from_checkpoint(
    user_id: str,
    thread_id: str,
    req: ReplayRunRequest,
    port: MarketplacePort,
) -> dict[str, Any]:
    if not thread_id.startswith(f"{user_id}:"):
        raise HTTPException(status_code=404, detail="Run thread not found or access denied")

    deps = NodeDeps(port=port)
    res = await replay(thread_id=thread_id, checkpoint_id=req.checkpoint_id, deps=deps)
    return res
