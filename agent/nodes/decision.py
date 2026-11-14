"""Decision agent node: pure deterministic function adjudicating bid-or-skip action."""
from __future__ import annotations

from typing import Any

from agent.handoffs import BidDecision
from agent.nodes.base import NodeDeps


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> BidDecision:
    """Evaluates risk, fit, and pricing reports to decide bid action."""
    raw_fit = state_slice.get("fit_report") or state_slice.get("fit") or {}
    raw_risk = state_slice.get("risk_report") or state_slice.get("risk") or {}
    raw_quote = state_slice.get("price_quote") or state_slice.get("quote")

    if isinstance(raw_fit, dict):
        fit_score = float(raw_fit.get("fit_score", 0.0))
    else:
        fit_score = float(getattr(raw_fit, "fit_score", 0.0))

    if isinstance(raw_risk, dict):
        risk_score = float(raw_risk.get("risk_score", 0.0))
        recommendation = str(raw_risk.get("recommendation", "ok"))
        risk_rationale = str(raw_risk.get("rationale", ""))
    else:
        risk_score = float(getattr(raw_risk, "risk_score", 0.0))
        recommendation = str(getattr(raw_risk, "recommendation", "ok"))
        risk_rationale = str(getattr(raw_risk, "rationale", ""))

    worth_connects = True
    connects_cost = 0
    if raw_quote:
        if isinstance(raw_quote, dict):
            worth_connects = bool(raw_quote.get("worth_connects", True))
            connects_cost = int(raw_quote.get("connects_cost", 0))
        else:
            worth_connects = bool(getattr(raw_quote, "worth_connects", True))
            connects_cost = int(getattr(raw_quote, "connects_cost", 0))

    cfg = deps.get_config()
    thresholds = cfg.get("thresholds", {})
    min_fit = float(thresholds.get("minimum_fit_score", 0.60))
    max_risk = float(thresholds.get("maximum_risk_score", 0.70))

    reasons: list[str] = []
    action: str = "skip"

    # Rule 1: Immediate block on risk recommendation
    if recommendation == "block":
        action = "skip"
        reasons.append(f"Blocked by safety policy: {risk_rationale}")
    # Rule 2: Maximum risk score breach
    elif risk_score > max_risk:
        action = "skip"
        reasons.append(f"Risk score ({risk_score:.2f}) exceeds configured ceiling ({max_risk:.2f}).")
    # Rule 3: Minimum fit score failure
    elif fit_score < min_fit:
        action = "skip"
        reasons.append(f"Fit score ({fit_score:.2f}) is below minimum required threshold ({min_fit:.2f}).")
    # Rule 4: Connects economics check
    elif not worth_connects:
        action = "skip"
        reasons.append(f"Financial expected value does not justify {connects_cost} Connects expenditure.")
    # Rule 5: Bid qualified
    else:
        action = "bid"
        reasons.append(
            f"Qualified: Fit score ({fit_score:.2f} >= {min_fit:.2f}) and Risk score ({risk_score:.2f} <= {max_risk:.2f}) meet standards."
        )

    return BidDecision(
        action=action,  # type: ignore[arg-type]
        reasons=reasons,
        thresholds_used={
            "minimum_fit_score": min_fit,
            "maximum_risk_score": max_risk,
        },
    )
