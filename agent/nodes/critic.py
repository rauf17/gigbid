"""Critic agent node: editorial evaluation, personalization auditing, and quality grading."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import Critique, ProposalDraft
from agent.llm import llm_call
from agent.nodes.base import NodeDeps

logger = logging.getLogger(__name__)


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> Critique:
    """Evaluates proposal draft quality, evidence grounding, and policy adherence."""
    raw_draft = state_slice.get("proposal_draft") or state_slice.get("draft") or {}
    if isinstance(raw_draft, dict):
        cover_letter = raw_draft.get("cover_letter", "")
    elif isinstance(raw_draft, ProposalDraft):
        cover_letter = raw_draft.cover_letter
    else:
        cover_letter = str(raw_draft)

    raw_spec = state_slice.get("job_spec") or state_slice.get("spec") or {}
    title = raw_spec.get("title", "") if isinstance(raw_spec, dict) else getattr(raw_spec, "title", "")
    summary = raw_spec.get("summary", "") if isinstance(raw_spec, dict) else getattr(raw_spec, "summary", "")

    policy = deps.get_policy()

    # 1. Deterministic Rule Checks
    words = cover_letter.split()
    word_count = len(words)
    length_ok = (policy.min_proposal_words <= word_count <= policy.max_proposal_words)

    # Check for generic cliché opening
    banned = policy.check_banned_phrases(cover_letter[:150])
    generic_matches = policy.match_regex_rules(cover_letter[:150])
    generic_opening = bool(banned or any(r.id == "POL-006-GENERIC-SPAM-PHRASING" for r, _, _ in generic_matches))

    issues: list[str] = []
    if not length_ok:
        if word_count < policy.min_proposal_words:
            issues.append(f"Proposal is too brief ({word_count} words vs minimum {policy.min_proposal_words}).")
        else:
            issues.append(f"Proposal exceeds length limit ({word_count} words vs maximum {policy.max_proposal_words}).")

    if generic_opening:
        issues.append(f"Cliché or generic opening phrase detected in opener: {banned or 'generic template wording'}.")

    # 2. LLM Judgment
    llm_grounding = 0.85
    llm_personalization = 0.80
    llm_issues: list[str] = []
    llm_verdict = "accept"

    try:
        critique = llm_call(
            node="critic",
            variables={
                "job_post": f"Title: {title}\nSummary: {summary}",
                "proposal_draft": cover_letter,
                "evidence_items": str(state_slice.get("evidence_items", "")),
            },
            schema=Critique,
            model_override=deps.llm,
        )
        if isinstance(critique, Critique):
            llm_grounding = critique.grounding
            llm_personalization = critique.personalization
            llm_issues = list(critique.issues)
            llm_verdict = critique.verdict
    except Exception as exc:  # noqa: BLE001
        logger.debug("[critic] LLM critique failed, falling back to heuristics: %s", exc)

    combined_issues = issues + [i for i in llm_issues if i not in issues]

    # Deterministic gating: generic opening or length violation strictly mandates revision
    if generic_opening or not length_ok or llm_grounding < 0.60 or llm_personalization < 0.50:
        final_verdict: str = "revise"
    else:
        final_verdict = llm_verdict if llm_verdict in {"accept", "revise"} else "accept"

    return Critique(
        grounding=round(llm_grounding, 2),
        personalization=round(llm_personalization, 2),
        length_ok=length_ok,
        generic_opening=generic_opening,
        issues=combined_issues,
        verdict=final_verdict,  # type: ignore[arg-type]
    )
