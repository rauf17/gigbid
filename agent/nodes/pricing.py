"""Pricing agent node: determines optimal bid amount and Connects expected value."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import PriceQuote
from agent.nodes.base import NodeDeps

logger = logging.getLogger(__name__)

PERSONA_FLOOR_RATES: dict[str, float] = {
    "ai_ml": 85.0,
    "fullstack": 65.0,
    "data_analyst": 55.0,
}


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> PriceQuote:
    """Calculates competitive bid quote and expected value."""
    raw_job = state_slice.get("job") or {}
    if hasattr(raw_job, "model_dump"):
        job = raw_job.model_dump()
    elif isinstance(raw_job, dict):
        job = raw_job
    else:
        job = {}

    persona = state_slice.get("persona") or "fullstack"
    budget = float(job.get("budget", 0.0) or 0.0)
    budget_type = str(job.get("budget_type", "fixed" if budget > 100 else "hourly")).lower()
    client_id = job.get("client_id")
    category = job.get("category")

    # Connects cost from job (default: 6 connects)
    connects_cost = int(job.get("connects_cost", 6) or 6)

    # 1. Freelancer Floor Rate
    floor_rate = PERSONA_FLOOR_RATES.get(persona, 60.0)

    # 2. Market stats via port.search_jobs
    market_budgets: list[float] = []
    if deps.port and category:
        try:
            comparables = await deps.port.search_jobs(category=category, limit=10)
            market_budgets = [float(c.budget) for c in comparables if c.budget and c.budget > 0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("[pricing] Failed searching comparable jobs: %s", exc)

    if market_budgets:
        market_avg = sum(market_budgets) / len(market_budgets)
    else:
        market_avg = budget if budget > 0 else (floor_rate * 20.0 if budget_type == "fixed" else floor_rate)

    # 3. Client historical metrics via port.get_client_history
    client_spend = 0.0
    hire_rate = 0.30
    if client_id and deps.port:
        try:
            ch = await deps.port.get_client_history(client_id)
            client_spend = float(ch.total_spent)
            hire_rate = float(ch.hire_rate)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[pricing] Failed fetching client history: %s", exc)

    # 4. Bid Amount Determination
    if budget_type == "hourly":
        if budget > 0:
            # Anchor near client budget while respecting freelancer floor
            bid_amount = max(floor_rate, min(budget, floor_rate * 1.35))
        else:
            bid_amount = floor_rate
        band_spread = 0.15
    else:  # fixed price
        if budget > 0:
            if client_spend > 5000.0 and hire_rate >= 0.50:
                bid_amount = budget  # Top-of-budget for premium client
            else:
                bid_amount = max(budget * 0.90, floor_rate * 10.0)
        else:
            bid_amount = max(market_avg, floor_rate * 15.0)
        band_spread = 0.12

    bid_amount = round(bid_amount, 2)
    band_low = round(bid_amount * (1.0 - band_spread), 2)
    band_high = round(bid_amount * (1.0 + band_spread), 2)

    # 5. Connects Expected Value Rule
    cfg = deps.get_config()
    pricing_cfg = cfg.get("pricing", {})
    connects_val_usd = float(pricing_cfg.get("connects_value_usd", 0.15))
    min_ev_ratio = float(pricing_cfg.get("min_ev_ratio", 2.0))

    connects_investment = connects_cost * connects_val_usd
    fit_score = float(state_slice.get("fit_report", {}).get("fit_score", 0.70) if isinstance(state_slice.get("fit_report"), dict) else getattr(state_slice.get("fit_report"), "fit_score", 0.70))

    # Win probability estimation based on fit and client hire rate
    estimated_win_prob = max(0.05, min(0.40, fit_score * hire_rate * 0.60))
    expected_revenue = bid_amount * estimated_win_prob
    ev_ratio = expected_revenue / max(0.01, connects_investment)
    worth_connects = (ev_ratio >= min_ev_ratio) and (bid_amount >= (floor_rate if budget_type == "hourly" else floor_rate * 5.0))

    rationale = (
        f"Bid ${bid_amount:,.2f} ({budget_type}); floor: ${floor_rate:.2f}/hr; "
        f"client spend: ${client_spend:,.2f} ({hire_rate:.1%}); "
        f"Connects: {connects_cost} (${connects_investment:.2f}); "
        f"EV ratio: {ev_ratio:.1f}x (req {min_ev_ratio:.1f}x)."
    )

    return PriceQuote(
        bid_amount=bid_amount,
        band_low=band_low,
        band_high=band_high,
        rationale=rationale,
        connects_cost=connects_cost,
        worth_connects=worth_connects,
    )
