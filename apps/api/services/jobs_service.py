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

    # Discover thread states for this user
    known_thread_ids: set[str] = set()
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s",
                (f"{user_id}:%",),
            )
            known_thread_ids = {r[0] for r in cur.fetchall()}
    except Exception as exc:  # noqa: BLE001
        logger.debug("[jobs_service] Checkpoints lookup failed: %s", exc)

    try:
        from agent.runtime import _GLOBAL_MEMORY_SAVER
        if hasattr(_GLOBAL_MEMORY_SAVER, "storage"):
            for k in _GLOBAL_MEMORY_SAVER.storage:
                tid = k if isinstance(k, str) else str(k)
                if tid.startswith(f"{user_id}:"):
                    known_thread_ids.add(tid)
    except Exception:  # noqa: BLE001, S110
        pass

    thread_states: dict[str, dict[str, Any]] = {}
    if known_thread_ids:
        try:
            from agent.graphs.bid_graph import build_bid_graph
            from agent.runtime import get_checkpointer_and_store

            async with get_checkpointer_and_store() as (cp, st):
                graph = build_bid_graph(checkpointer=cp, store=st)
                for j in jobs:
                    tid = f"{user_id}:{j.id}"
                    if tid in known_thread_ids:
                        snap = await graph.aget_state({"configurable": {"thread_id": tid}})
                        if snap and snap.values:
                            thread_states[j.id] = dict(snap.values)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[jobs_service] Failed loading thread states: %s", exc)

    summaries: list[JobSummaryResponse] = []

    for j in jobs:
        st = thread_states.get(j.id)
        if st:
            fit_obj = st.get("fit")
            fit_score = getattr(fit_obj, "score", None) if fit_obj else st.get("fit_score")
            risk_obj = st.get("risk")
            risk_score = getattr(risk_obj, "scam_score", None) if risk_obj else st.get("risk_score")
            trust_score = getattr(risk_obj, "client_trust_score", None) if risk_obj else None
            is_scam = getattr(risk_obj, "is_scam", False) if risk_obj else False
            scam_reasons = getattr(risk_obj, "reasons", []) if risk_obj else []
            scam_reason = "; ".join(scam_reasons) if scam_reasons else None
            dec_obj = st.get("decision")
            rec_action = getattr(dec_obj, "action", "pending") if dec_obj else "pending"
            skip_reason = st.get("skip_reason") or (getattr(dec_obj, "rationale", None) if rec_action == "skip" else None)
            quote_obj = st.get("quote")
            quote = getattr(quote_obj, "bid_amount", None) if quote_obj else None
            status_val = st.get("status", "awaiting_approval")
            risk_badges = getattr(risk_obj, "reasons", []) if risk_obj else []
        else:
            status_val = "skipped" if j.id in skipped_ids else "not_analysed"
            fit_score = None
            risk_score = None
            trust_score = None
            is_scam = False
            scam_reason = None
            rec_action = "skip" if j.id in skipped_ids else "pending"
            quote = None
            risk_badges = []
            skip_reason = _MEMORY_JOB_SKIPS.get((user_id, j.id), {}).get("reason") if j.id in skipped_ids else None

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
                description=getattr(j, "description", "") or "",
                client_name=client_str,
                client_id=getattr(j, "client_id", None) or client_str,
                client_country=getattr(j, "client_country", None),
                category=j.category,
                budget=budget_val,
                budget_min=getattr(j, "budget_min", None),
                budget_max=getattr(j, "budget_max", None),
                budget_type=getattr(j, "budget_type", "fixed"),
                connects_cost=j.connects_cost,
                fit_score=fit_score,
                risk_score=risk_score,
                client_trust_score=trust_score,
                risk_badges=risk_badges,
                recommended_action=rec_action,
                quote=quote,
                status=status_val,
                skip_reason=skip_reason,
                is_scam=is_scam,
                scam_reason=scam_reason,
                created_at=getattr(j, "created_at", None) or getattr(j, "posted_at", None),
                posted_at=getattr(j, "posted_at", None),
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
        budget_min=getattr(j, "budget_min", None),
        budget_max=getattr(j, "budget_max", None),
        budget_type=getattr(j, "budget_type", "fixed"),
        connects_cost=j.connects_cost,
        client_name=client_str,
        client_id=getattr(j, "client_id", None) or client_str,
        client_country=getattr(j, "client_country", None),
        category=j.category,
        status=last_run_state.get("status", "not_analysed") if last_run_state else "not_analysed",
        posted_at=getattr(j, "posted_at", None),
        risk_report=risk_report,
        requirement_evidence_matrix=req_matrix,
        price_rationale=price_rationale,
        decision_reasoning=decision_reasoning,
        last_run=last_run_state,
    )
