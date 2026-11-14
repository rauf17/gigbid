"""Fit Matcher agent node: matches JobSpec requirements to verified portfolio evidence."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import FitMatrixRow, FitReport, JobSpec
from agent.nodes.base import NodeDeps
from rag.retriever import get_retriever

logger = logging.getLogger(__name__)


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> FitReport:
    """Matches JobSpec requirements to verified portfolio evidence."""
    raw_spec = state_slice.get("job_spec")
    if isinstance(raw_spec, dict):
        spec = JobSpec.model_validate(raw_spec)
    elif isinstance(raw_spec, JobSpec):
        spec = raw_spec
    else:
        # Fallback empty spec
        spec = JobSpec(
            title="Unknown",
            summary="",
            requirements=[],
            skills=state_slice.get("job", {}).get("skills", []),
        )

    persona = state_slice.get("persona") or "ai_ml"

    # Resolve retriever
    retriever = deps.retriever
    if retriever is None:
        retriever = get_retriever(persona=persona)

    matrix: list[FitMatrixRow] = []
    gaps: list[str] = []
    reasons: list[str] = []
    weighted_strengths: list[float] = []

    # Evaluate each atomic requirement
    for req in spec.requirements:
        req_query = f"{req.text} {' '.join(spec.skills[:3])}".strip()
        try:
            hits = await retriever.retrieve(
                query=req_query,
                k=5,
                filters={"persona": persona},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[fit_matcher] Retrieval failed for requirement '%s': %s", req.id, exc)
            hits = []

        if hits:
            best_score = max(h.score for h in hits)
            evidence_ids = [h.id for h in hits[:3]]

            # Map retrieval score to strength
            if best_score >= 0.35:
                strength: str = "strong"
                weighted_strengths.append(1.0 if req.kind == "must_have" else 0.8)
                reasons.append(f"Strong match for '{req.text[:40]}...' using [{', '.join(evidence_ids[:2])}].")
            elif best_score >= 0.10:
                strength = "weak"
                weighted_strengths.append(0.5 if req.kind == "must_have" else 0.4)
                reasons.append(f"Partial match for '{req.text[:40]}...' using [{evidence_ids[0]}].")
            else:
                strength = "none"
                weighted_strengths.append(0.0)
                gaps.append(req.text)
                reasons.append(f"No strong evidence found for '{req.text[:40]}...'.")

            matrix.append(
                FitMatrixRow(
                    requirement_id=req.id,
                    evidence_ids=evidence_ids,
                    strength=strength,  # type: ignore[arg-type]
                )
            )
        else:
            matrix.append(
                FitMatrixRow(
                    requirement_id=req.id,
                    evidence_ids=[],
                    strength="none",
                )
            )
            weighted_strengths.append(0.0)
            gaps.append(req.text)
            reasons.append(f"Missing evidence for requirement: {req.text}")

    # Compute coverage-weighted fit score
    total_reqs = len(spec.requirements)
    if total_reqs > 0:
        raw_score = sum(weighted_strengths) / float(total_reqs)
        fit_score = max(0.0, min(1.0, raw_score))
    else:
        # Fallback if no decomposed requirements
        fit_score = 0.50

    return FitReport(
        matrix=matrix,
        fit_score=round(fit_score, 2),
        gaps=gaps,
        reasons=reasons[:8],
    )
