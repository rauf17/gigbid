"""Claim splitting and grounding verification engine (Assignment R5 / Prompt 8 Part 3)."""
from __future__ import annotations

import logging
import re
from typing import Any

from agent.handoffs import ClaimCheck
from agent.llm import llm_call
from rag.retriever import EvidenceItem

logger = logging.getLogger(__name__)


def split_claims(text: str) -> list[str]:
    """Deterministically splits proposal text into atomic verifiable factual sentences.

    Filters out conversational greetings, closing salutations, and screening headers.
    """
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    claims: list[str] = []

    skip_patterns = [
        r"(?i)^(?:hi|hello|dear|greetings)\b",
        r"(?i)^(?:best|regards|sincerely|thanks|thank\s+you)\b",
        r"(?i)^(?:looking\s+forward|let\s+me\s+know|feel\s+free)\b",
        r"(?i)^i\s+look\s+forward\s+to\b",
    ]

    for s in raw_sentences:
        clean = s.strip()
        if len(clean) < 15:
            continue
        if any(re.search(pat, clean) for pat in skip_patterns):
            continue
        claims.append(clean)

    return claims


def judge_claim_support(
    claim: str,
    evidence_items: list[EvidenceItem | dict[str, Any]],
    llm: Any | None = None,
) -> ClaimCheck:
    """Judges whether a claim is supported, partial, or unsupported by evidence."""
    if not evidence_items:
        return ClaimCheck(
            claim=claim,
            status="unsupported",
            evidence_ids=[],
            rationale="No supporting evidence items provided.",
        )

    # Extract inline markers e.g. [E:cs_aiml_001] or [cs_aiml_001]
    cited_ids = re.findall(r"\[(?:E:)?([a-zA-Z0-9_\-]+)\]", claim)

    # Format evidence text for evaluation
    evidence_corpus = []
    item_map: dict[str, str] = {}
    for ev in evidence_items:
        if isinstance(ev, dict):
            iid = ev.get("id", "")
            txt = ev.get("text", "")
        else:
            iid = getattr(ev, "id", "")
            txt = getattr(ev, "text", "")
        evidence_corpus.append(f"[{iid}]: {txt}")
        item_map[iid] = txt

    # If LLM is provided or active, perform LLM grounding check
    if llm is not None:
        try:
            verdict = llm_call(
                node="verifier",
                variables={
                    "proposal_draft": claim,
                    "evidence_items": "\n".join(evidence_corpus[:5]),
                },
                schema=ClaimCheck,
                model_override=llm,
            )
            if isinstance(verdict, ClaimCheck):
                return verdict
        except Exception as exc:  # noqa: BLE001
            logger.debug("[verify] LLM claim verification failed: %s", exc)

    # Deterministic lexical and citation check
    matching_ids = []
    claim_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", claim)}

    for cid in cited_ids:
        if cid in item_map:
            matching_ids.append(cid)

    # Check keyword overlap against evidence corpus
    best_overlap = 0.0
    best_id = ""
    for cid, txt in item_map.items():
        ev_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", txt)}
        overlap = len(claim_words & ev_words) / max(1, len(claim_words))
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = cid

    if best_overlap >= 0.40 or matching_ids:
        matched = list(set(matching_ids + ([best_id] if best_id and best_overlap >= 0.35 else [])))
        return ClaimCheck(
            claim=claim,
            status="supported",
            evidence_ids=matched,
            rationale=f"Claim verified with {best_overlap:.1%} vocabulary overlap against [{', '.join(matched)}].",
        )
    elif best_overlap >= 0.18:
        matched = [best_id] if best_id else []
        return ClaimCheck(
            claim=claim,
            status="partial",
            evidence_ids=matched,
            rationale=f"Claim partially supported ({best_overlap:.1%} overlap) by [{best_id}].",
        )
    else:
        return ClaimCheck(
            claim=claim,
            status="unsupported",
            evidence_ids=[],
            rationale=f"No matching evidence found in portfolio (best overlap only {best_overlap:.1%}).",
        )


def clean_draft(
    draft_text: str,
    checks: list[ClaimCheck],
) -> tuple[str, list[str], list[str]]:
    """Removes unsupported claims and rewrites partial ones from the cover letter.

    Returns:
        (cleaned_text, removed_claims, rewritten_claims)
    """
    cleaned_text = draft_text
    removed: list[str] = []
    rewritten: list[str] = []

    for check in checks:
        if check.status == "unsupported":
            # Remove sentence completely
            if check.claim in cleaned_text:
                cleaned_text = cleaned_text.replace(check.claim, "").strip()
                removed.append(check.claim)
            else:
                # Fuzzy sentence removal if whitespace differs
                pattern = re.escape(check.claim)
                cleaned_text = re.sub(pattern, "", cleaned_text).strip()
                removed.append(check.claim)
        elif check.status == "partial" and check.claim in cleaned_text:
            # Rewriting: strip unverified hyperbolic metrics/claims or qualify
            rewritten_sentence = re.sub(
                r"\b(?:guaranteed|100%|top\s+spot|#1|proven\s+world-class)\b",
                "demonstrated",
                check.claim,
                flags=re.IGNORECASE,
            )
            if rewritten_sentence != check.claim:
                cleaned_text = cleaned_text.replace(check.claim, rewritten_sentence)
                rewritten.append(rewritten_sentence)

    # Clean double spaces and empty lines resulting from removal
    cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"  +", " ", cleaned_text).strip()

    return cleaned_text, removed, rewritten
