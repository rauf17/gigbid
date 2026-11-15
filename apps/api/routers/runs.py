"""Router for starting runs, state inspection, SSE live updates, and replay."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from agent.marketplace_port import MarketplacePort
from agent.nodes.base import NodeDeps
from apps.api.auth.deps import current_user
from apps.api.deps import get_marketplace_port
from apps.api.schemas.auth import UserResponse
from apps.api.schemas.runs import (
    CreateRunRequest,
    ReplayRunRequest,
    RunCreateResponse,
    RunStateResponse,
    RunTraceResponse,
)
from apps.api.services.runs_service import (
    get_run_state,
    get_run_trace,
    replay_run_from_checkpoint,
    start_run,
)
from apps.api.streaming import create_sse_response

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunCreateResponse, operation_id="create_bid_run")
async def create_run(
    req: CreateRunRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> RunCreateResponse:
    """Starts the LangGraph bid pipeline in a background task, returning the thread ID immediately."""
    persona = req.persona_id or user.persona_id
    return await start_run(
        user_id=user.id,
        job_id=req.job_id,
        persona_id=persona,
        port=port,
        background_tasks=background_tasks,
    )


@router.get("/{thread_id}", response_model=RunStateResponse, operation_id="get_run_state_by_id")
async def get_state(
    thread_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
) -> RunStateResponse:
    """Returns state summary, active node, and approval status for the given thread."""
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    return await get_run_state(user_id=user.id, thread_id=actual_thread_id)


@router.get("/{thread_id}/stream", operation_id="stream_run_execution")
async def stream_run(
    thread_id: str,
    request: Request,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
    last_event_id: Annotated[str | None, Header(description="Last received SSE ID on reconnect")] = None,
) -> EventSourceResponse:
    """Server-Sent Events endpoint streaming live graph node updates, token usage, and status changes."""
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    job_id = actual_thread_id.split(":", 1)[1] if ":" in actual_thread_id else actual_thread_id
    try:
        job = await port.get_job(job_id)
        job_dict = job.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed retrieving job {job_id}: {exc}") from exc

    deps = NodeDeps(port=port)
    return create_sse_response(
        request=request,
        job=job_dict,
        thread_id=actual_thread_id,
        user_id=user.id,
        persona_id=user.persona_id,
        deps=deps,
        last_event_id=last_event_id,
    )


@router.get("/{thread_id}/trace", response_model=RunTraceResponse, operation_id="get_run_trace_log")
async def get_trace(
    thread_id: str,
    user: Annotated[UserResponse, Depends(current_user)],
) -> RunTraceResponse:
    """Returns the append-only audit trace for the specified run thread, with optional LangSmith link."""
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    return await get_run_trace(user_id=user.id, thread_id=actual_thread_id)


@router.post("/{thread_id}/replay", response_model=dict, operation_id="replay_run_checkpoint")
async def replay_run(
    thread_id: str,
    req: ReplayRunRequest,
    user: Annotated[UserResponse, Depends(current_user)],
    port: Annotated[MarketplacePort, Depends(get_marketplace_port)],
) -> dict:
    """Re-executes the bid graph from a specified historical checkpoint."""
    actual_thread_id = thread_id if thread_id.startswith(f"{user.id}:") else f"{user.id}:{thread_id}"
    return await replay_run_from_checkpoint(user_id=user.id, thread_id=actual_thread_id, req=req, port=port)
