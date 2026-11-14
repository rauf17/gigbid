"""Claim splitting, normalization, and grounding verification engine (Assignment R5 / Prompt 8 & Prompt 9).

Strengthened deterministic checks before LLM judgment:
(a) Every cited [E:id] must exist in the persona corpus (normalizing IDs like cs_aiml_001 to ai_ml_cs_cs_aiml_001).
(b) Every number, percentage, or metric in a claim must appear in the cited evidence text, otherwise unsupported.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from agent.handoffs import ClaimCheck
from agent.llm import llm_call
from rag.retriever import EvidenceItem

logger = logging.getLogger(__name__)

DEFAULT_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "data" / "personas"
_PERSONA_CORPUS_CACHE: dict[str, dict[str, Any]] = {}


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


def get_persona_corpus(persona: str, personas_dir: Path | None = None) -> dict[str, Any]:
    """Loads and caches all known chunk IDs and text for a persona corpus."""
    if persona in _PERSONA_CORPUS_CACHE:
        return _PERSONA_CORPUS_CACHE[persona]

    p_dir = (personas_dir or DEFAULT_PERSONAS_DIR) / persona
    known_ids: set[str] = set()
    corpus_map: dict[str, str] = {}

    if p_dir.is_dir():
        try:
            from rag.ingest.chunkers import build_chunks_for_persona

            chunks = build_chunks_for_persona(persona, p_dir)
            for c in chunks:
                known_ids.add(c.id)
                corpus_map[c.id] = c.text

                # Also register short ID aliases (e.g. cs_aiml_001 from ai_ml_cs_cs_aiml_001)
                if c.type == "case_study":
                    short_id = c.id.replace(f"{persona}_cs_", "")
                    known_ids.add(short_id)
                    corpus_map[short_id] = c.text
                elif c.type == "review":
                    short_id = c.id.replace(f"{persona}_rev_", "review_")
                    known_ids.add(short_id)
                    corpus_map[short_id] = c.text
                elif "repo" in c.type:
                    short_id = c.id.replace(f"{persona}_repo_", "")
                    known_ids.add(short_id)
                    corpus_map[short_id] = c.text
        except Exception as exc:  # noqa: BLE001
            logger.debug("[verify] Could not build full persona chunks: %s", exc)

    cache_data = {"known_ids": known_ids, "corpus_map": corpus_map}
    _PERSONA_CORPUS_CACHE[persona] = cache_data
    return cache_data


def extract_claim_metrics(claim_text: str) -> list[str]:
    """Extracts numerical quantities, percentages, latencies, and metrics from a claim."""
    # Strip citation brackets first so [E:cs_aiml_001] doesn't treat 001 as a metric
    clean = re.sub(r"\[(?:E:)?([a-zA-Z0-9_\-]+)\]", "", claim_text)

    metrics: list[str] = []
    # 1. Percentages (e.g. 98%, 91.5%)
    percentages = re.findall(r"\b\d+(?:\.\d+)?%", clean)
    metrics.extend(percentages)

    # 2. Currency (e.g. $2,500, $50)
    currency = re.findall(r"\$\d+(?:,\d+)*(?:\.\d+)?", clean)
    metrics.extend(currency)

    # 3. Quantified metrics with units (e.g. 4.5M, 100ms, 45GB, 10k)
    quantities = re.findall(
        r"\b\d+(?:\.\d+)?\s*(?:[MmKk]|ms|s|pages?|users?|gb|tb|tbps|mbps)\b",
        clean,
        re.IGNORECASE,
    )
    metrics.extend(quantities)

    # 4. Standalone floats or multi-digit numbers (excluding common 4-digit years 1990-2040)
    numbers = re.findall(r"\b\d+\.\d+\b|\b\d{2,}\b", clean)
    for n in numbers:
        if n.isdigit() and 1990 <= int(n) <= 2040:
            continue
        if not any(n in m for m in metrics):
            metrics.append(n)

    return metrics


def judge_claim_support(
    claim: str,
    evidence_items: list[EvidenceItem | dict[str, Any]],
    llm: Any | None = None,
    persona: str | None = None,
) -> ClaimCheck:
    """Judges whether a claim is supported, partial, or unsupported by evidence.

    Enforces strict deterministic checks before calling LLM:
    (a) Cited [E:id] must exist in the persona corpus or provided evidence items.
    (b) Every number/metric in the claim must appear in the cited evidence text.
    """
    if not evidence_items and not persona:
        return ClaimCheck(
            claim=claim,
            status="unsupported",
            evidence_ids=[],
            rationale="No supporting evidence items provided.",
        )

    # Extract inline markers e.g. [E:cs_aiml_001] or [cs_aiml_001]
    cited_ids = re.findall(r"\[(?:E:)?([a-zA-Z0-9_\-]+)\]", claim)

    # Build local item map from provided evidence_items
    item_map: dict[str, str] = {}
    for ev in evidence_items:
        if isinstance(ev, dict):
            iid = ev.get("id", "")
            txt = ev.get("text", "")
        else:
            iid = getattr(ev, "id", "")
            txt = getattr(ev, "text", "")
        item_map[iid] = txt

    # Load persona corpus if persona specified
    p_corpus = get_persona_corpus(persona) if persona else {"known_ids": set(), "corpus_map": {}}
    known_corpus_ids: set[str] = p_corpus["known_ids"]
    corpus_text_map: dict[str, str] = p_corpus["corpus_map"]

    # -------------------------------------------------------------------------
    # Deterministic Check A: Valid Citation Existence
    # -------------------------------------------------------------------------
    valid_cited_ids: list[str] = []
    for cid in cited_ids:
        # Check in provided evidence items or in full persona corpus
        if cid in item_map:
            valid_cited_ids.append(cid)
        elif cid in known_corpus_ids:
            valid_cited_ids.append(cid)
            item_map[cid] = corpus_text_map.get(cid, "")
        else:
            # Check normalized persona prefixes e.g. ai_ml_cs_cs_aiml_001
            norm_id = f"{persona}_cs_{cid}" if persona else ""
            if norm_id in known_corpus_ids:
                valid_cited_ids.append(norm_id)
                item_map[norm_id] = corpus_text_map.get(norm_id, "")
            elif persona:
                # Cited an ID that does NOT exist anywhere in the persona corpus
                return ClaimCheck(
                    claim=claim,
                    status="unsupported",
                    evidence_ids=[],
                    rationale=f"Cited evidence ID '{cid}' does not exist in persona portfolio.",
                )

    # -------------------------------------------------------------------------
    # Deterministic Check B: Number / Metric Verification
    # -------------------------------------------------------------------------
    metrics = extract_claim_metrics(claim)
    if metrics:
        # Collect evidence text against which numbers are checked
        if valid_cited_ids:
            searchable_text = " ".join(item_map.get(cid, "") for cid in valid_cited_ids)
        elif item_map:
            searchable_text = " ".join(item_map.values())
        else:
            searchable_text = ""

        for metric in metrics:
            clean_metric = metric.strip().replace("$", "")
            # Also extract the raw number without % or units (e.g. "98" from "98%", "4.5" from "4.5M")
            raw_num_match = re.search(r"\d+(?:\.\d+)?", clean_metric)
            raw_num = raw_num_match.group(0) if raw_num_match else clean_metric

            # Check if metric or raw number appears in evidence text
            metric_present = (metric in searchable_text) or (clean_metric in searchable_text) or (raw_num in searchable_text)
            if not metric_present:
                return ClaimCheck(
                    claim=claim,
                    status="unsupported",
                    evidence_ids=[],
                    rationale=f"Metric/number '{metric}' in claim does not appear in cited evidence text.",
                )

    # -------------------------------------------------------------------------
    # Semantic & Lexical Grounding Check
    # -------------------------------------------------------------------------
    evidence_corpus = [f"[{iid}]: {txt}" for iid, txt in item_map.items()]

    # If LLM is provided, perform LLM grounding check
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

    # Deterministic vocabulary overlap check
    claim_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", claim)}
    best_overlap = 0.0
    best_id = ""

    for cid, txt in item_map.items():
        ev_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", txt)}
        overlap = len(claim_words & ev_words) / max(1, len(claim_words))
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = cid

    if best_overlap >= 0.40 or valid_cited_ids:
        matched = list(set(valid_cited_ids + ([best_id] if best_id and best_overlap >= 0.35 else [])))
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
