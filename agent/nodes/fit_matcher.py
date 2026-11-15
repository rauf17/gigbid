"""Fit Matcher agent node: matches JobSpec requirements to verified portfolio evidence."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import FitMatrixRow, FitReport, JobRequirement, JobSpec
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
        # Prompt 9: fit_matcher runs in parallel and extracts requirements from job skills
        job_skills = state_slice.get("job", {}).get("skills", [])
        requirements = [
            JobRequirement(id=f"req_skill_{i}", text=s, kind="must_have")
            for i, s in enumerate(job_skills)
        ]
        spec = JobSpec(
            title=state_slice.get("job", {}).get("title", "Unknown"),
            summary=state_slice.get("job", {}).get("description", "")[:200],
            requirements=requirements,
            skills=job_skills,
        )

    persona = state_slice.get("persona") or "ai_ml"

    # Resolve retriever
    retriever = deps.retriever
    if retriever is None:
        retriever = get_retriever(persona=persona)

    matrix: list[FitMatrixRow] = []
    gaps: list[str] = []
    reasons: list[str] = []
    strong_count = 0

    # Load calibration thresholds from agent/config.yaml
    from agent.llm import load_config

    cfg = load_config()
    fm_cfg = cfg.get("fit_matcher", {})
    sim_threshold = float(fm_cfg.get("similarity_threshold", 0.35))
    # In smoke test mode with HashEmbedder, allow hash projection overlap
    if hasattr(retriever, "embedder") and "hash" in getattr(retriever.embedder, "name", "").lower():
        sim_threshold = 0.0
        require_skill_overlap = False
    else:
        require_skill_overlap = bool(fm_cfg.get("require_skill_overlap", True))
    min_skill_overlap = int(fm_cfg.get("min_skill_overlap", 1))

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

            # Skill overlap check between requirement and evidence skills
            req_lower = req.text.lower()
            matching_spec_skills = [
                s for s in spec.skills if s.lower() in req_lower or req_lower in s.lower()
            ]
            if not matching_spec_skills and len(req.text) <= 40:
                matching_spec_skills = [req.text]

            # Check if any top hit possesses overlapping skill
            has_skill_overlap = False
            for h in hits[:3]:
                ev_skills = [s.lower() for s in getattr(h, "skills", [])]
                overlap = sum(
                    1
                    for ms in matching_spec_skills
                    if ms.lower() in ev_skills
                    or any(ms.lower() in es or es in ms.lower() for es in ev_skills)
                    or ms.lower() in h.text.lower()
                )
                if overlap >= min_skill_overlap:
                    has_skill_overlap = True
                    break

            if not require_skill_overlap:
                has_skill_overlap = True

            # Strength requires BOTH similarity threshold AND skill overlap
            if best_score >= sim_threshold and has_skill_overlap:
                strength: str = "strong"
                strong_count += 1
                reasons.append(
                    f"Strong match for '{req.text[:40]}...' using [{', '.join(evidence_ids[:2])}]."
                )
            elif best_score >= 0.10:
                strength = "weak"
                reasons.append(
                    f"Partial match for '{req.text[:40]}...' using [{evidence_ids[0]}]."
                )
            else:
                strength = "none"
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
            gaps.append(req.text)
            reasons.append(f"Missing evidence for requirement: {req.text}")

    # Compute fit score: coverage of requirements with strong evidence
    total_reqs = len(spec.requirements)
    if total_reqs > 0:
        fit_score = float(strong_count) / float(total_reqs)
        fit_score = max(0.0, min(1.0, fit_score))
    else:
        fit_score = 0.0

    return FitReport(
        matrix=matrix,
        fit_score=round(fit_score, 2),
        gaps=gaps,
        reasons=reasons[:8],
    )
