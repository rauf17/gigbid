"""Runtime execution, durability, checkpoint replay, and approval state tracking.

Assignment requirements:
- Part 3 of Prompt 9 (C1, C2, C4, C5, C6, C7, R3, R4, R7).
- run_job(job, user_id, persona_id) starts a thread (thread_id = f"{user_id}:{job.id}").
- resume(thread_id, decision) resumes with Command(resume=decision).
- pending_approvals(user_id) lists threads awaiting approval from checkpoints.
- replay(thread_id, checkpoint_id) re-executes from historical checkpoint.
- history(thread_id) lists checkpoint snapshots.
- Graceful in-memory fallback if Postgres is offline.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command

from agent.db import get_db_url
from agent.graphs.bid_graph import build_bid_graph
from agent.nodes.base import NodeDeps
from agent.state import BidGraphState, BidStatus

logger = logging.getLogger(__name__)

# Ensure Windows Selector loop policy for async psycopg operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_GLOBAL_MEMORY_SAVER = MemorySaver()
_GLOBAL_MEMORY_STORE = InMemoryStore()


@asynccontextmanager
async def get_checkpointer_and_store(
    conn_string: str | None = None,
) -> AsyncIterator[tuple[BaseCheckpointSaver, BaseStore]]:
    """Yields active async Postgres checkpointer and store, falling back to memory."""
    url = (conn_string or get_db_url()).replace("postgresql+psycopg://", "postgresql://")
    try:
        async with (
            AsyncPostgresSaver.from_conn_string(url) as saver,
            AsyncPostgresStore.from_conn_string(url) as store,
        ):
            await saver.setup()
            await store.setup()
            yield saver, store
            return
    except Exception as exc:  # noqa: BLE001
        logger.debug("[runtime] Postgres unreachable, falling back to in-memory checkpointer: %s", exc)
        yield _GLOBAL_MEMORY_SAVER, _GLOBAL_MEMORY_STORE


async def run_job(
    job: dict[str, Any],
    user_id: str = "default_user",
    persona_id: str = "ai_ml",
    deps: NodeDeps | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> dict[str, Any]:
    """Starts or continues a thread, executing until it interrupts or completes."""
    job_id = job.get("id") or uuid4().hex
    thread_id = f"{user_id}:{job_id}"
    active_deps = deps or NodeDeps()

    if checkpointer is not None and store is not None:
        graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=active_deps)
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id, "deps": active_deps}}
        init_state: BidGraphState = {
            "job": job,
            "user_id": user_id,
            "persona_id": persona_id,
            "trace_id": uuid4().hex,
            "budget": {"steps": 0, "tokens": 0},
        }
        await graph.ainvoke(init_state, config=config)
        state_snap = await graph.aget_state(config)
        return dict(state_snap.values)

    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st, deps=active_deps)
        config = {"configurable": {"thread_id": thread_id, "deps": active_deps}}
        init_state = {
            "job": job,
            "user_id": user_id,
            "persona_id": persona_id,
            "trace_id": uuid4().hex,
            "budget": {"steps": 0, "tokens": 0},
        }
        await graph.ainvoke(init_state, config=config)
        state_snap = await graph.aget_state(config)
        return dict(state_snap.values)


async def resume(
    thread_id: str,
    decision: dict[str, Any],
    deps: NodeDeps | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> dict[str, Any]:
    """Resumes an interrupted graph execution using Command(resume=decision)."""
    active_deps = deps or NodeDeps()
    cmd = Command(resume=decision)

    if checkpointer is not None and store is not None:
        graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=active_deps)
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id, "deps": active_deps}}
        res = await graph.ainvoke(cmd, config=config)
        return dict(res)

    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st, deps=active_deps)
        config = {"configurable": {"thread_id": thread_id, "deps": active_deps}}
        res = await graph.ainvoke(cmd, config=config)
        return dict(res)


async def pending_approvals(
    user_id: str,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> list[dict[str, Any]]:
    """Lists threads awaiting human approval so page refreshes never drop pending reviews."""
    pending: list[dict[str, Any]] = []
    prefix = f"{user_id}:"

    # Query matching thread IDs from Postgres if available
    thread_ids: list[str] = []
    try:
        import psycopg

        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s",
                (f"{prefix}%",),
            )
            rows = cur.fetchall()
            thread_ids = [r[0] for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug("[runtime] Failed fetching thread list from postgres: %s", exc)

    if checkpointer is not None and store is not None:
        graph = build_bid_graph(checkpointer=checkpointer, store=store)
        for tid in thread_ids:
            config = {"configurable": {"thread_id": tid}}
            snap = await graph.aget_state(config)
            is_awaiting = (
                "approval" in snap.next
                or snap.values.get("status") == BidStatus.AWAITING_APPROVAL
                or any(t.interrupts for t in snap.tasks)
            )
            if is_awaiting:
                payload = snap.tasks[0].interrupts[0].value if (snap.tasks and snap.tasks[0].interrupts) else {}
                pending.append(
                    {
                        "thread_id": tid,
                        "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                        "payload": payload,
                        "created_at": snap.created_at,
                    }
                )
        return pending

    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st)
        for tid in thread_ids:
            config = {"configurable": {"thread_id": tid}}
            snap = await graph.aget_state(config)
            is_awaiting = (
                "approval" in snap.next
                or snap.values.get("status") == BidStatus.AWAITING_APPROVAL
                or any(t.interrupts for t in snap.tasks)
            )
            if is_awaiting:
                payload = snap.tasks[0].interrupts[0].value if (snap.tasks and snap.tasks[0].interrupts) else {}
                pending.append(
                    {
                        "thread_id": tid,
                        "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                        "payload": payload,
                        "created_at": snap.created_at,
                    }
                )
    return pending


async def replay(
    thread_id: str,
    checkpoint_id: str,
    deps: NodeDeps | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> dict[str, Any]:
    """Re-executes the graph pipeline from a historical checkpoint id."""
    active_deps = deps or NodeDeps()
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "deps": active_deps,
        }
    }

    if checkpointer is not None and store is not None:
        graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=active_deps)
        res = await graph.ainvoke(None, config=config)
        return dict(res)

    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st, deps=active_deps)
        res = await graph.ainvoke(None, config=config)
        return dict(res)


async def history(
    thread_id: str,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> list[dict[str, Any]]:
    """Returns chronological checkpoint snapshots for the specified thread."""
    results: list[dict[str, Any]] = []
    config = {"configurable": {"thread_id": thread_id}}

    if checkpointer is not None and store is not None:
        graph = build_bid_graph(checkpointer=checkpointer, store=store)
        async for snap in graph.aget_state_history(config):
            results.append(
                {
                    "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                    "step": snap.metadata.get("step") if snap.metadata else 0,
                    "source": snap.metadata.get("source") if snap.metadata else "",
                    "status": snap.values.get("status"),
                    "created_at": snap.created_at,
                    "next": list(snap.next),
                }
            )
        return results

    async with get_checkpointer_and_store() as (cp, st):
        graph = build_bid_graph(checkpointer=cp, store=st)
        async for snap in graph.aget_state_history(config):
            results.append(
                {
                    "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                    "step": snap.metadata.get("step") if snap.metadata else 0,
                    "source": snap.metadata.get("source") if snap.metadata else "",
                    "status": snap.values.get("status"),
                    "created_at": snap.created_at,
                    "next": list(snap.next),
                }
            )
    return results
