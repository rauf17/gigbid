"""LangGraph Store wrapper managing long-term style rules and outcome memory.

Assignment requirements:
- Part 4 of Prompt 9.
- Namespaces:
  1. ("style", user_id): learned user preferences and editorial patterns.
  2. ("outcome", user_id, category): historical smoothed win rates.
- Strict promotion rules: never raw unvetted tool output.
- User inspection and deletion API: list_memory, delete_memory_item.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from agent.db import write_audit_trace
from agent.llm import llm_call
from agent.memory.promotion_rules import (
    CandidateStyleRule,
    OutcomeStatsItem,
    PromotionDecision,
    StyleRuleItem,
    compute_smoothed_outcome,
    evaluate_style_candidate,
)
from agent.nodes.base import NodeDeps

logger = logging.getLogger(__name__)


class MemoryItem(BaseModel):
    """User-inspectable memory item stored in long-term memory."""

    namespace: tuple[str, ...] = Field(..., description="Memory namespace tuple.")
    key: str = Field(..., description="Unique key in namespace.")
    value: dict[str, Any] = Field(..., description="Stored payload.")
    created_at: str | None = None
    updated_at: str | None = None


class ExtractedRulePayload(BaseModel):
    """Structured output expected from extract_style_rule prompt."""

    has_rule: bool = False
    pattern_key: str = ""
    rule_text: str = ""
    polarity: str = "positive"
    scope: str = "cover_letter"


async def get_style_rules(user_id: str, store: BaseStore) -> list[StyleRuleItem]:
    """Retrieves all promoted style rules for the specified user."""
    namespace = ("style", user_id)
    items = await store.asearch(namespace, limit=50)
    rules: list[StyleRuleItem] = []
    for it in items:
        try:
            rules.append(StyleRuleItem.model_validate(it.value))
        except Exception as exc:  # noqa: BLE001
            logger.debug("[memory] Skipping malformed style rule %s: %s", it.key, exc)
    return rules


async def get_style_notes_for_writer(user_id: str, store: BaseStore) -> str:
    """Formats all promoted style rules for injection into the writer node prompt."""
    rules = await get_style_rules(user_id, store)
    if not rules:
        return ""
    lines = [f"- {r.rule_text}" for r in rules if r.rule_text]
    return "\n".join(lines)


async def record_proposal_edit(
    user_id: str,
    original_text: str,
    edited_text: str,
    edit_id: str,
    store: BaseStore,
    deps: NodeDeps | None = None,
    trace_id: str = "",
    reason: str = "",
) -> PromotionDecision:
    """Extracts a candidate rule from a proposal diff and tests for promotion."""
    active_deps = deps or NodeDeps()
    cfg = active_deps.get_config()
    min_obs = int(cfg.get("memory", {}).get("min_observations", 2))

    # 1. Run extraction prompt
    try:
        extracted = llm_call(
            node="extract_style_rule",
            variables={
                "original_text": original_text,
                "edited_text": edited_text,
                "edit_reason": reason or "User edited draft proposal before submission.",
            },
            schema=ExtractedRulePayload,
            model_override=active_deps.llm,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[memory] LLM extraction failed: %s", exc)
        return PromotionDecision(
            promoted=False,
            reason=f"Extraction failed: {exc}",
            observed_count=0,
        )

    if not isinstance(extracted, ExtractedRulePayload) or not extracted.has_rule:
        return PromotionDecision(
            promoted=False,
            reason="No generalizable style rule found in diff.",
            observed_count=0,
        )

    candidate = CandidateStyleRule(
        pattern_key=extracted.pattern_key or "general_style",
        rule_text=extracted.rule_text,
        polarity="negative" if extracted.polarity == "negative" else "positive",
        scope=extracted.scope or "cover_letter",
        edit_id=edit_id,
    )

    # 2. Fetch existing promoted and pending rules
    existing_promoted = await get_style_rules(user_id, store)

    pending_ns = ("pending_style", user_id)
    pending_items = await store.asearch(pending_ns, limit=100)
    pending_candidates: list[CandidateStyleRule] = []
    for it in pending_items:
        try:
            pending_candidates.append(CandidateStyleRule.model_validate(it.value))
        except Exception:  # noqa: BLE001
            logger.debug("[memory] Skipping malformed pending item %s", it.key)

    # 3. Evaluate promotion rules
    decision = evaluate_style_candidate(
        candidate=candidate,
        existing_promoted=existing_promoted,
        pending_observations=pending_candidates,
        min_observations=min_obs,
    )

    # 4. Handle results
    if decision.conflicting_rule_id is not None:
        # Contradiction detected: reject and log to audit trace
        write_audit_trace(
            trace_id=trace_id,
            thread_id=f"{user_id}:memory",
            node_name="memory",
            observation=(
                f"Contradiction rejected: candidate rule '{candidate.pattern_key}' "
                f"conflicts with rule '{decision.conflicting_rule_id}'."
            ),
        )
        return decision

    if decision.promoted and decision.rule is not None:
        # Promote to long-term store
        await store.aput(
            ("style", user_id),
            decision.rule.id,
            decision.rule.model_dump(),
        )
        # Clean up pending entries for this pattern
        cand_key = candidate.pattern_key.lower().replace("-", "_").strip()
        for it in pending_items:
            if it.value.get("pattern_key", "").lower().replace("-", "_").strip() == cand_key:
                await store.adelete(pending_ns, it.key)

        write_audit_trace(
            trace_id=trace_id,
            thread_id=f"{user_id}:memory",
            node_name="memory",
            observation=f"Promoted long-term style rule: {decision.rule.id}",
        )
    else:
        # Save as pending candidate
        key = f"{candidate.pattern_key}_{edit_id}"
        await store.aput(pending_ns, key, candidate.model_dump())

    return decision


async def record_outcome(
    user_id: str,
    category: str,
    outcome_type: str,
    store: BaseStore,
    deps: NodeDeps | None = None,
) -> OutcomeStatsItem | None:
    """Updates category win/reply rates using Laplace smoothing."""
    active_deps = deps or NodeDeps()
    min_outcomes = int(active_deps.get_config().get("memory", {}).get("min_outcomes", 3))

    raw_ns = ("raw_outcomes", user_id)
    raw_item = await store.aget(raw_ns, category)
    counts = raw_item.value if raw_item else {"bids": 0, "replies": 0, "hires": 0}

    counts["bids"] = counts.get("bids", 0) + 1
    if outcome_type == "reply":
        counts["replies"] = counts.get("replies", 0) + 1
    elif outcome_type == "hire":
        counts["replies"] = counts.get("replies", 0) + 1
        counts["hires"] = counts.get("hires", 0) + 1

    await store.aput(raw_ns, category, counts)

    smoothed = compute_smoothed_outcome(
        category=category,
        bids=counts["bids"],
        replies=counts["replies"],
        hires=counts["hires"],
        min_outcomes=min_outcomes,
    )

    if smoothed is not None:
        await store.aput(
            ("outcome", user_id, category),
            category,
            smoothed.model_dump(),
        )

    return smoothed


async def list_memory(
    user_id: str,
    namespace: str | None = None,
    store: BaseStore | None = None,
) -> list[MemoryItem]:
    """Lists long-term memory items for a user, allowing full inspection."""
    if store is None:
        return []

    results: list[MemoryItem] = []
    namespaces_to_query: list[tuple[str, ...]] = []

    if namespace == "style":
        namespaces_to_query.append(("style", user_id))
    elif namespace == "outcome":
        namespaces_to_query.append(("outcome", user_id))
    else:
        namespaces_to_query.extend([("style", user_id), ("outcome", user_id)])

    for ns in namespaces_to_query:
        items = await store.asearch(ns, limit=100)
        for it in items:
            results.append(
                MemoryItem(
                    namespace=it.namespace,
                    key=it.key,
                    value=it.value,
                    created_at=str(it.created_at) if it.created_at else None,
                    updated_at=str(it.updated_at) if it.updated_at else None,
                )
            )
    return results


async def delete_memory_item(
    user_id: str,
    namespace: str,
    key: str,
    store: BaseStore,
) -> bool:
    """Deletes a long-term memory item on user request."""
    if namespace == "style":
        ns = ("style", user_id)
        await store.adelete(ns, key)
        return True
    if namespace == "outcome":
        ns = ("outcome", user_id, key)
        await store.adelete(ns, key)
        return True
    return False
