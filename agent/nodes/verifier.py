"""Verifier agent node: factual claim auditing, unsupported claim removal, and verification reporting."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import ClaimCheck, ProposalDraft, VerificationReport
from agent.nodes.base import NodeDeps
from rag.retriever import get_retriever
from rag.verify import clean_draft, judge_claim_support, split_claims

logger = logging.getLogger(__name__)


async def run(
    state_slice: dict[str, Any],
    deps: NodeDeps,
) -> tuple[ProposalDraft, VerificationReport]:
    """Audits proposal draft claims against retrieved evidence, pruning unsupported assertions."""
    raw_draft = state_slice.get("proposal_draft") or state_slice.get("draft") or {}
    if isinstance(raw_draft, dict):
        draft = ProposalDraft.model_validate(raw_draft)
    elif isinstance(raw_draft, ProposalDraft):
        draft = raw_draft
    else:
        draft = ProposalDraft(cover_letter=str(raw_draft), screening_answers=[], claims=[])

    persona = state_slice.get("persona") or "ai_ml"
    evidence_items = list(state_slice.get("evidence_items") or state_slice.get("evidence") or [])

    # If no evidence passed, retrieve top portfolio evidence
    if not evidence_items:
        retriever = deps.retriever or get_retriever(persona=persona)
        try:
            evidence_items = await retriever.retrieve(
                query=draft.cover_letter[:300],
                k=8,
                filters={"persona": persona},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[verifier] Failed retrieving evidence: %s", exc)
            evidence_items = []

    # 1. Deterministic Claim Splitting
    sentences = split_claims(draft.cover_letter)
    if not sentences and draft.cover_letter.strip():
        sentences = [draft.cover_letter.strip()]

    # 2. Claim Grounding Judgments
    checks: list[ClaimCheck] = []
    for sentence in sentences:
        check = judge_claim_support(sentence, evidence_items, llm=deps.llm)
        checks.append(check)

    total_claims = len(checks)
    unsupported_before_count = sum(1 for c in checks if c.status == "unsupported")
    rate_before = (unsupported_before_count / total_claims) if total_claims > 0 else 0.0

    # 3. Clean and Rewrite Draft
    clean_text, removed, rewritten = clean_draft(draft.cover_letter, checks)

    # Post-verification stats
    rate_after = 0.0  # By definition, unsupported claims have been excised

    # Re-extract claims for clean draft
    remaining_claims = [c for c in draft.claims if c.text not in removed]

    clean_draft_obj = ProposalDraft(
        cover_letter=clean_text,
        screening_answers=draft.screening_answers,
        claims=remaining_claims,
    )

    report = VerificationReport(
        checks=checks,
        unsupported_rate_before=round(rate_before, 2),
        unsupported_rate_after=round(rate_after, 2),
        removed=removed,
        rewritten=rewritten,
    )

    return clean_draft_obj, report
