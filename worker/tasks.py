"""Arq background tasks: autonomous scouting, job deduplication, and bid analysis."""
from __future__ import annotations

import logging
from typing import Any

from agent.db import get_all_proposal_submissions, get_proposal_submission
from agent.marketplace_port import McpMarketplacePort
from agent.nodes.base import NodeDeps
from agent.runtime import run_job
from apps.api.auth.service import get_marketplace_token, get_user_profile

logger = logging.getLogger(__name__)

DEFAULT_WEEKLY_CONNECTS_BUDGET = 40
DEFAULT_MAX_PROPOSALS_PER_DAY = 10


def check_budget_and_limits(user_id: str) -> bool:
    """Verifies user has not exceeded their weekly Connects budget or daily proposal limit."""
    profile = get_user_profile(user_id)
    weekly_budget = profile.get("weekly_connects_budget", DEFAULT_WEEKLY_CONNECTS_BUDGET)
    max_per_day = DEFAULT_MAX_PROPOSALS_PER_DAY

    submissions = get_all_proposal_submissions()
    prefix = f"{user_id}:"
    user_subs = [s for s in submissions if s.get("thread_id", "").startswith(prefix)]

    # Estimate connects spent (each proposal submission uses connects, default 4)
    connects_spent = len(user_subs) * 4
    if connects_spent >= weekly_budget:
        logger.warning(
            "[worker] User %s exceeded weekly Connects budget (%s >= %s)",
            user_id,
            connects_spent,
            weekly_budget,
        )
        return False

    if len(user_subs) >= max_per_day:
        logger.warning(
            "[worker] User %s exceeded daily proposal limit (%s >= %s)",
            user_id,
            len(user_subs),
            max_per_day,
        )
        return False

    return True


async def scout_saved_search(ctx: dict[str, Any], user_id: str, search_id: str) -> dict[str, Any]:
    """Polls marketplace jobs for a user's saved search, dedupes, and enqueues analyse_job."""
    if not check_budget_and_limits(user_id):
        return {"status": "skipped", "reason": "budget_exhausted", "enqueued": 0}

    profile = get_user_profile(user_id)
    token = get_marketplace_token(user_id)
    port = ctx.get("port") or McpMarketplacePort(user_id=user_id, token=token)

    saved_searches = profile.get("saved_searches") or []
    target_search: dict[str, Any] = next(
        (s for s in saved_searches if s.get("id") == search_id),
        {"category": profile.get("persona_id", "ai_ml"), "query": None},
    )

    try:
        jobs = await port.search_jobs(
            category=target_search.get("category"),
            query=target_search.get("query"),
            limit=10,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[worker] scout_saved_search failed for %s: %s", user_id, exc)
        return {"status": "error", "message": str(exc), "enqueued": 0}

    redis = ctx.get("redis")
    enqueued_count = 0

    for j in jobs:
        dedupe_key = f"job_scouted:{user_id}:{j.id}"
        # Atomic Redis idempotency check
        if redis is not None:
            is_new = await redis.set(dedupe_key, "1", nx=True, ex=86400 * 7)
            if not is_new:
                continue

        # Check Postgres proposal submissions
        existing_sub = get_proposal_submission(f"{user_id}:{j.id}")
        if existing_sub:
            continue

        if redis is not None:
            await redis.enqueue_job("analyse_job", user_id, j.id, _job_id=f"analyse:{user_id}:{j.id}")
        enqueued_count += 1

    return {"status": "ok", "user_id": user_id, "search_id": search_id, "enqueued": enqueued_count}


async def analyse_job(ctx: dict[str, Any], user_id: str, job_id: str) -> dict[str, Any]:
    """Autonomous pipeline run for a single candidate job, pausing at human approval."""
    redis = ctx.get("redis")
    idempotency_key = f"job_analysed:{user_id}:{job_id}"

    # Verify idempotency in Redis
    if redis is not None:
        is_first = await redis.set(idempotency_key, "1", nx=True, ex=86400 * 7)
        if not is_first:
            logger.info("[worker] Skipping duplicate analysis for %s:%s", user_id, job_id)
            return {"status": "already_analysed", "job_id": job_id}

    # Verify idempotency in Postgres submissions
    thread_id = f"{user_id}:{job_id}"
    if get_proposal_submission(thread_id):
        logger.info("[worker] Proposal already exists for %s", thread_id)
        return {"status": "already_submitted", "thread_id": thread_id}

    if not check_budget_and_limits(user_id):
        return {"status": "skipped", "reason": "budget_exhausted", "job_id": job_id}

    profile = get_user_profile(user_id)
    token = get_marketplace_token(user_id)
    port = ctx.get("port") or McpMarketplacePort(user_id=user_id, token=token)

    try:
        job = await port.get_job(job_id)
        job_dict = job.model_dump()
    except Exception as exc:  # noqa: BLE001
        logger.error("[worker] Failed fetching job %s for analysis: %s", job_id, exc)
        return {"status": "error", "error": str(exc), "job_id": job_id}

    deps = NodeDeps(port=port)
    persona = profile.get("persona_id", "ai_ml")
    res = await run_job(job=job_dict, user_id=user_id, persona_id=persona, deps=deps)

    return {
        "status": "completed",
        "thread_id": thread_id,
        "run_status": res.get("status"),
        "fit_score": res.get("fit_score"),
    }


async def cron_scout_all(ctx: dict[str, Any]) -> dict[str, Any]:
    """Periodic cron job scouting all saved searches for active tenants."""
    import psycopg

    from agent.db import _MEMORY_USERS, get_db_url

    user_ids: list[str] = []
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM users")
            user_ids = [r[0] for r in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        logger.debug("[worker.cron] DB lookup failed, falling back to memory: %s", exc)
        user_ids = list(_MEMORY_USERS.keys())

    redis = ctx.get("redis")
    scouted_users = 0
    for uid in user_ids:
        prof = get_user_profile(uid)
        searches = prof.get("saved_searches") or [{"id": "default"}]
        for s in searches:
            sid = s.get("id", "default")
            if redis is not None:
                await redis.enqueue_job("scout_saved_search", uid, sid)
            scouted_users += 1

    return {"status": "ok", "scouted_searches": scouted_users}
