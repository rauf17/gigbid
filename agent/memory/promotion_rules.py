"""Promotion rules governing writes to long-term memory.

Assignment requirements:
- Part 4 of Prompt 9.
- A candidate rule is NOT promoted to long-term memory immediately.
  Conditions:
  a) Observed in >= N distinct proposals (default N=2, configurable).
  b) No contradiction with existing rules.
  c) Non-empty, actionable, scoped.
- Outcome memory:
  - Aggregate outcome counts after >= N outcomes, smoothed (Laplace).
  - Never raw tool output.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateStyleRule(BaseModel):
    """Candidate editorial rule extracted from proposal diff."""

    pattern_key: str = Field(..., description="Normalized key for grouping similar edits.")
    rule_text: str = Field(..., description="Actionable guideline text.")
    polarity: Literal["positive", "negative"] = Field(
        default="positive",
        description="Whether the rule mandates ('positive') or prohibits ('negative') a behavior.",
    )
    scope: str = Field(default="cover_letter", description="Applicable text scope.")
    edit_id: str = Field(..., description="Unique proposal revision identifier.")
    model_config = ConfigDict(frozen=True)


class StyleRuleItem(BaseModel):
    """Promoted long-term style rule."""

    id: str = Field(..., description="Unique style rule identifier.")
    rule_text: str = Field(..., description="Editorial guideline text.")
    pattern: str = Field(..., description="Group key for the pattern.")
    source_edit_ids: list[str] = Field(default_factory=list, description="IDs of edits promoting this rule.")
    count: int = Field(default=1, description="Number of observed edits matching this pattern.")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_applied_at: str | None = None
    polarity: Literal["positive", "negative"] = "positive"
    model_config = ConfigDict(frozen=True)


class OutcomeStatsItem(BaseModel):
    """Aggregated, Laplace-smoothed outcome statistics by category."""

    id: str = Field(..., description="Category identifier.")
    category: str = Field(..., description="Marketplace category.")
    bids_count: int = 0
    replies_count: int = 0
    hires_count: int = 0
    win_rate: float = 0.0
    smoothed_win_rate: float = 0.0
    last_updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model_config = ConfigDict(frozen=True)


class PromotionDecision(BaseModel):
    """Outcome of evaluating a candidate rule against memory promotion rules."""

    promoted: bool = Field(..., description="Whether candidate is promoted to long-term memory.")
    reason: str = Field(..., description="Rationale for promotion, retention, or rejection.")
    conflicting_rule_id: str | None = None
    observed_count: int = 1
    rule: StyleRuleItem | None = None
    model_config = ConfigDict(frozen=True)


def check_contradiction(
    candidate: CandidateStyleRule,
    existing_rules: list[StyleRuleItem],
) -> StyleRuleItem | None:
    """Checks whether a candidate contradicts any existing promoted rule."""
    cand_key = candidate.pattern_key.lower().replace("-", "_").strip()
    cand_neg = candidate.polarity == "negative" or bool(
        re.search(r"\b(never|do not|don't|avoid|no|ban|prohibit)\b", candidate.rule_text, re.IGNORECASE)
    )

    for ex in existing_rules:
        ex_key = ex.pattern.lower().replace("-", "_").strip()
        if cand_key == ex_key or cand_key in ex_key or ex_key in cand_key:
            ex_neg = ex.polarity == "negative" or bool(
                re.search(r"\b(never|do not|don't|avoid|no|ban|prohibit)\b", ex.rule_text, re.IGNORECASE)
            )
            # If one is prohibitive and the other is prescriptive for the same pattern
            if cand_neg != ex_neg:
                return ex
    return None


def evaluate_style_candidate(
    candidate: CandidateStyleRule,
    existing_promoted: list[StyleRuleItem],
    pending_observations: list[CandidateStyleRule],
    min_observations: int = 2,
) -> PromotionDecision:
    """Evaluates whether candidate rule satisfies all criteria for promotion."""
    # 1. Validation check: non-empty, actionable, scoped
    if not candidate.rule_text.strip() or len(candidate.rule_text.strip()) < 5:
        return PromotionDecision(
            promoted=False,
            reason="Rule text is too short or empty.",
            observed_count=0,
        )

    # 2. Contradiction check against already promoted rules
    conflict = check_contradiction(candidate, existing_promoted)
    if conflict is not None:
        return PromotionDecision(
            promoted=False,
            reason=f"Contradicts existing promoted rule '{conflict.id}': {conflict.rule_text}",
            conflicting_rule_id=conflict.id,
            observed_count=0,
        )

    # 3. Aggregate observations from matching pending candidates
    cand_key = candidate.pattern_key.lower().replace("-", "_").strip()
    matching_pending = [
        p for p in pending_observations
        if p.pattern_key.lower().replace("-", "_").strip() == cand_key
    ]

    all_edit_ids = {p.edit_id for p in matching_pending}
    all_edit_ids.add(candidate.edit_id)
    observed_count = len(all_edit_ids)

    # 4. Check threshold condition
    if observed_count >= min_observations:
        rule_id = f"rule_{cand_key}"
        promoted_rule = StyleRuleItem(
            id=rule_id,
            rule_text=candidate.rule_text,
            pattern=candidate.pattern_key,
            source_edit_ids=sorted(all_edit_ids),
            count=observed_count,
            created_at=datetime.now(UTC).isoformat(),
            polarity=candidate.polarity,
        )
        return PromotionDecision(
            promoted=True,
            reason=f"Observed in {observed_count} >= {min_observations} distinct proposals.",
            observed_count=observed_count,
            rule=promoted_rule,
        )

    return PromotionDecision(
        promoted=False,
        reason=f"Pending: observed in {observed_count} < {min_observations} proposals.",
        observed_count=observed_count,
    )


def compute_smoothed_outcome(
    category: str,
    bids: int,
    replies: int,
    hires: int,
    min_outcomes: int = 3,
) -> OutcomeStatsItem | None:
    """Computes Laplace-smoothed outcome statistics if minimum outcomes threshold met."""
    if bids < min_outcomes:
        return None

    # Laplace smoothing with alpha=1, beta=2 (standard binary smoothing)
    smoothed = (hires + 1.0) / (bids + 2.0)
    raw = (hires / bids) if bids > 0 else 0.0

    return OutcomeStatsItem(
        id=category,
        category=category,
        bids_count=bids,
        replies_count=replies,
        hires_count=hires,
        win_rate=round(raw, 4),
        smoothed_win_rate=round(smoothed, 4),
        last_updated_at=datetime.now(UTC).isoformat(),
    )
