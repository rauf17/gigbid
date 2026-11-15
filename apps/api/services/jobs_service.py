"""Service layer for job search, inbox triage joining, and skipping."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import psycopg

from agent.db import _MEMORY_JOB_SKIPS, get_db_url
from agent.marketplace_port import MarketplacePort, MarketplaceUnavailable
from apps.api.deps import handle_marketplace_error
from apps.api.schemas.jobs import JobDetailResponse, JobSummaryResponse

logger = logging.getLogger(__name__)


def record_job_skip(user_id: str, job_id: str, reason: str) -> None:
    try:
        url = get_db_url()
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO job_skips (user_id, job_id, reason) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id, job_id) DO UPDATE SET reason = EXCLUDED.reason, created_at = NOW()",
                (user_id, job_id, reason),
            )
    except (psycopg.Error, OSError) as exc:
        logger.debug("[jobs_service] Postgres record_job_skip failed: %s", exc)

    _MEMORY_JOB_SKIPS[(user_id, job_id)] = {"user_id": user_id, "job_id": job_id, "reason": reason}


def get_skipped_job_ids(user_id: str) -> set[str]:
    skipped: set[str] = set()
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT job_id FROM job_skips WHERE user_id = %s", (user_id,))
            skipped = {r[0] for r in cur.fetchall()}
            return skipped
    except (psycopg.Error, OSError) as exc:
        logger.debug("[jobs_service] Postgres get_skipped_job_ids failed: %s", exc)

    for (u, j) in _MEMORY_JOB_SKIPS:
        if u == user_id:
            skipped.add(j)
    return skipped


async def list_jobs(
    user_id: str,
    port: MarketplacePort,
    category: str | None = None,
    min_fit: float | None = None,
    status_filter: str | None = None,
    limit: int = 20,
) -> list[JobSummaryResponse]:
    """Fetches candidate jobs from marketplace, joins with triage data and filters."""
    try:
        jobs = await port.search_jobs(category=category, limit=limit)
    except (MarketplaceUnavailable, httpx.HTTPError, OSError) as exc:
        handle_marketplace_error(exc, queued=False)
        return []

    skipped_ids = get_skipped_job_ids(user_id)
    summaries: list[JobSummaryResponse] = []

    for j in jobs:
        status_val = "skipped" if j.id in skipped_ids else "new"
        fit_score: float | None = None
        risk_score: float | None = None
        risk_badges: list[str] = []
        rec_action = "skip" if j.id in skipped_ids else "pending"
        quote: float | None = None

        if status_filter and status_val != status_filter:
            continue
        if min_fit is not None and (fit_score is None or fit_score < min_fit):
            continue

        client_str = getattr(j, "client_name", "") or getattr(j, "client_id", "") or ""
        budget_val = getattr(j, "budget", None) or getattr(j, "budget_max", None)

        summaries.append(
            JobSummaryResponse(
                id=j.id,
                title=j.title,
                client_name=client_str,
                category=j.category,
                budget=budget_val,
                connects_cost=j.connects_cost,
                fit_score=fit_score,
                risk_score=risk_score,
                risk_badges=risk_badges,
                recommended_action=rec_action,
                quote=quote,
                status=status_val,
                created_at=getattr(j, "created_at", None) or getattr(j, "posted_at", None),
            )
        )

    # Sort by fit_score descending (None sorted last)
    summaries.sort(key=lambda s: s.fit_score if s.fit_score is not None else -1.0, reverse=True)
    return summaries


async def get_job_detail(
    user_id: str,
    job_id: str,
    port: MarketplacePort,
) -> JobDetailResponse:
    """Fetches full job specifications, risk analysis, and stored graph decision."""
    try:
        j = await port.get_job(job_id)
    except Exception as exc:
        handle_marketplace_error(exc, queued=False)
        raise

    # Look up last run state if exists
    thread_id = f"{user_id}:{job_id}"
    last_run_state: dict[str, Any] | None = None
    risk_report: dict[str, Any] = {}
    req_matrix: list[dict[str, Any]] = []
    price_rationale: dict[str, Any] = {}
    decision_reasoning = ""

    from agent.graphs.bid_graph import build_bid_graph
    from agent.runtime import get_checkpointer_and_store

    try:
        async with get_checkpointer_and_store() as (cp, st):
            graph = build_bid_graph(checkpointer=cp, store=st)
            snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
            if snap and snap.values:
                last_run_state = {
                    "thread_id": thread_id,
                    "status": snap.values.get("status"),
                    "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                }
                risk_report = snap.values.get("risk_report") or {}
                req_matrix = snap.values.get("requirement_evidence_matrix") or []
                price_rationale = snap.values.get("price_rationale") or {}
                decision_reasoning = snap.values.get("decision_reasoning") or ""
    except (psycopg.Error, OSError, ValueError, KeyError) as exc:
        logger.debug("[jobs_service] Could not load thread state for %s: %s", thread_id, exc)

    client_str = getattr(j, "client_name", "") or getattr(j, "client_id", "") or ""
    budget_val = getattr(j, "budget", None) or getattr(j, "budget_max", None)

    return JobDetailResponse(
        id=j.id,
        title=j.title,
        description=j.description,
        skills=j.skills,
        budget=budget_val,
        connects_cost=j.connects_cost,
        client_name=client_str,
        category=j.category,
        risk_report=risk_report,
        requirement_evidence_matrix=req_matrix,
        price_rationale=price_rationale,
        decision_reasoning=decision_reasoning,
        last_run=last_run_state,
    )
