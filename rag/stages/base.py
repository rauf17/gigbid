"""Common utilities, rollup helpers, and RRF algorithms for RAG pipeline stages."""
from __future__ import annotations

import re
from typing import Any

from rag.schema import Chunk

DEFAULT_EXPERIENCE_TYPES = ["case_study", "repo_readme", "repo_code", "review", "cv"]

ALL_KNOWN_REPOS = {
    "llm-guardrails",
    "rag-eval-pipeline",
    "realtime-ops-dashboard",
    "saas-subscription-core",
    "dbt-analytics-warehouse",
    "kpi-executive-dashboard",
}


def roll_up_to_item_id(chunk_id: str) -> str:
    """Rolls up fine-grained chunk IDs to item/project-level IDs.

    - CV: {persona}_cv_xxx -> {persona}_cv
    - Repo: {persona}_repo_{repo_name}_xxx -> {persona}_repo_{repo_name}
    - Case study: {persona}_cs_{id} (already item-level)
    - Review: {persona}_review_{id} (already item-level)
    - Proposal: {persona}_prop_{id} (already item-level)
    """
    m_cv = re.match(r"^([a-z_]+_cv)_\d+$", chunk_id)
    if m_cv:
        return m_cv.group(1)

    for rname in ALL_KNOWN_REPOS:
        prefix = f"_repo_{rname}"
        if prefix in chunk_id:
            persona = chunk_id.split(prefix)[0]
            return f"{persona}{prefix}"

    m_repo = re.match(r"^([a-z_]+_repo_[a-zA-Z0-9\-]+?)_(?:readme|[a-zA-Z0-9_]+)_\d+$", chunk_id)
    if m_repo:
        return m_repo.group(1)

    return chunk_id


def compute_rrf_scores(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> dict[str, float]:
    """Computes Reciprocal Rank Fusion scores across multiple ranked lists of item IDs.

    RRF(d) = sum_{r in R} (1.0 / (k + rank_r(d)))
    """
    scores: dict[str, float] = {}
    for rlist in ranked_lists:
        for rank, item_id in enumerate(rlist, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (float(k) + float(rank)))
    return scores


def chunk_to_evidence_dict(chunk: Chunk, score: float = 0.0) -> dict[str, Any]:
    """Converts a Chunk instance to a dictionary representation for an EvidenceItem."""
    item_id = roll_up_to_item_id(chunk.id)
    return {
        "id": item_id,
        "raw_chunk_id": chunk.id,
        "type": chunk.type,
        "source": chunk.source_path,
        "project": chunk.project,
        "date": chunk.date,
        "outcome": chunk.outcome,
        "text": chunk.text,
        "score": float(score),
        "skills": chunk.skills,
    }
