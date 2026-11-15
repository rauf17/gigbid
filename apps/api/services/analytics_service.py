"""Service layer for analytics metrics, connects accounting, and cost aggregations."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import psycopg

from agent.accounting import load_call_logs
from agent.db import _MEMORY_JOB_SKIPS, get_all_proposal_submissions, get_db_url
from apps.api.schemas.analytics import (
    AnalyticsResponse,
    CategoryOutcomeItem,
    ConnectsUsageItem,
    CostLatencyItem,
)

logger = logging.getLogger(__name__)


def _get_top_rejection_reasons(user_id: str) -> list[dict[str, Any]]:
    reasons: list[str] = []
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT reason FROM job_skips WHERE user_id = %s", (user_id,))
            reasons = [r[0] for r in cur.fetchall() if r[0]]
    except (psycopg.Error, OSError) as exc:
        logger.debug("[analytics_service] Postgres query rejection reasons failed: %s", exc)

    if not reasons:
        for (u, _), item in _MEMORY_JOB_SKIPS.items():
            if u == user_id and item.get("reason"):
                reasons.append(item["reason"])

    counts = Counter(reasons)
    return [{"reason": reason, "count": count} for reason, count in counts.most_common(5)]


async def get_analytics_report(user_id: str) -> AnalyticsResponse:
    # 1. Proposal and Connects outcomes
    submissions = get_all_proposal_submissions()
    prefix = f"{user_id}:"
    user_subs = [s for s in submissions if s.get("thread_id", "").startswith(prefix)]

    by_category: dict[str, dict[str, int]] = {}
    for s in user_subs:
        cat = s.get("persona_id") or "ai_ml"
        by_category.setdefault(cat, {"bids": 0, "replies": 0, "hires": 0, "connects": 0})
        by_category[cat]["bids"] += 1
        by_category[cat]["connects"] += 4  # Standard connects per job
        st = (s.get("status") or "").lower()
        if st in {"replied", "interview"}:
            by_category[cat]["replies"] += 1
        elif st in {"hired", "won"}:
            by_category[cat]["replies"] += 1
            by_category[cat]["hires"] += 1

    outcome_items: list[CategoryOutcomeItem] = []
    connects_items: list[ConnectsUsageItem] = []

    for cat, stats in by_category.items():
        bids = stats["bids"]
        replies = stats["replies"]
        hires = stats["hires"]
        outcome_items.append(
            CategoryOutcomeItem(
                category=cat,
                bids=bids,
                replies=replies,
                hires=hires,
                reply_rate=round(replies / bids, 3) if bids > 0 else 0.0,
                hire_rate=round(hires / bids, 3) if bids > 0 else 0.0,
            )
        )
        connects_items.append(
            ConnectsUsageItem(
                category=cat,
                connects_spent=stats["connects"],
                proposals_submitted=bids,
                hires_won=hires,
            )
        )

    # 2. LLM Cost and Latency
    logs = load_call_logs()
    by_model: dict[str, dict[str, Any]] = {}
    for entry in logs:
        m = entry.get("model") or "unknown"
        by_model.setdefault(m, {"calls": 0, "tokens": 0, "cost": 0.0, "latencies": []})
        by_model[m]["calls"] += 1
        by_model[m]["tokens"] += int(entry.get("prompt_tokens", 0)) + int(entry.get("completion_tokens", 0))
        by_model[m]["cost"] += float(entry.get("estimated_cost_usd", 0.0))
        if not entry.get("cache_hit", False):
            by_model[m]["latencies"].append(float(entry.get("latency_ms", 0.0)))

    cost_items: list[CostLatencyItem] = []
    for m, data in by_model.items():
        lats = data["latencies"]
        avg_lat = round(sum(lats) / len(lats), 1) if lats else 0.0
        cost_items.append(
            CostLatencyItem(
                model=m,
                total_calls=data["calls"],
                total_tokens=data["tokens"],
                total_cost_usd=round(data["cost"], 5),
                avg_latency_ms=avg_lat,
            )
        )

    # 3. Top rejection reasons
    top_reasons = _get_top_rejection_reasons(user_id)

    return AnalyticsResponse(
        outcomes_by_category=outcome_items,
        connects_spent_vs_outcomes=connects_items,
        cost_and_latency=cost_items,
        top_rejection_reasons=top_reasons,
    )
