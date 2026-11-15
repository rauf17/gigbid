"""Server-Sent Events (SSE) bridge for real-time bid graph streaming."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from agent.graphs.bid_graph import build_bid_graph, stream_bid
from agent.nodes.base import NodeDeps
from agent.runtime import get_checkpointer_and_store

logger = logging.getLogger(__name__)


async def sse_event_generator(
    request: Request,
    job: dict[str, Any],
    thread_id: str,
    user_id: str,
    persona_id: str,
    deps: NodeDeps,
    last_event_id: str | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Yields formatted SSE message dicts over LangGraph 'updates' and 'custom' stream modes."""
    event_seq = 0

    # If client reconnected with Last-Event-ID, emit the current checkpoint state first
    if last_event_id:
        try:
            async with get_checkpointer_and_store() as (cp, st):
                graph = build_bid_graph(checkpointer=cp, store=st)
                snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
                if snap and snap.values:
                    event_seq += 1
                    yield {
                        "event": "reconnect",
                        "id": f"{thread_id}:{event_seq}",
                        "data": json.dumps({
                            "type": "checkpoint_state",
                            "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                            "status": snap.values.get("status"),
                            "current_node": snap.next[0] if snap.next else None,
                        }),
                    }
        except Exception as exc:  # noqa: BLE001
            logger.debug("[streaming] Reconnect checkpoint lookup failed: %s", exc)

    try:
        async with get_checkpointer_and_store() as (cp, st):
            async for mode, chunk in stream_bid(
                job=job,
                thread_id=thread_id,
                user_id=user_id,
                persona_id=persona_id,
                checkpointer=cp,
                store=st,
                deps=deps,
            ):
                if await request.is_disconnected():
                    logger.info("[streaming] Client disconnected from thread %s", thread_id)
                    break

                event_seq += 1
                ev_id = f"{thread_id}:{event_seq}"

                if mode == "updates" and isinstance(chunk, dict):
                    for node_name, updates in chunk.items():
                        payload = {
                            "node": node_name,
                            "updates": {k: v for k, v in updates.items() if k not in {"job"}},
                        }
                        yield {
                            "event": "node_update",
                            "id": ev_id,
                            "data": json.dumps(payload),
                        }
                elif mode == "custom":
                    yield {
                        "event": "custom",
                        "id": ev_id,
                        "data": json.dumps(chunk if isinstance(chunk, dict) else {"data": chunk}),
                    }

        # Final terminal event
        event_seq += 1
        yield {
            "event": "final",
            "id": f"{thread_id}:{event_seq}",
            "data": json.dumps({"thread_id": thread_id, "status": "stream_completed"}),
        }

    except asyncio.CancelledError:
        logger.info("[streaming] SSE stream cancelled cleanly for %s", thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("[streaming] Stream error for %s: %s", thread_id, exc)
        yield {
            "event": "error",
            "id": f"{thread_id}:{event_seq + 1}",
            "data": json.dumps({"error": str(exc)}),
        }


def create_sse_response(
    request: Request,
    job: dict[str, Any],
    thread_id: str,
    user_id: str,
    persona_id: str,
    deps: NodeDeps,
    last_event_id: str | None = None,
) -> EventSourceResponse:
    """Builds a Starlette EventSourceResponse with 15s heartbeats."""
    generator = sse_event_generator(
        request=request,
        job=job,
        thread_id=thread_id,
        user_id=user_id,
        persona_id=persona_id,
        deps=deps,
        last_event_id=last_event_id,
    )
    return EventSourceResponse(generator, ping=15)
