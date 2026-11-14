"""Analyst agent node: parses raw job postings into structured JobSpec hand-offs."""
from __future__ import annotations

import logging
from typing import Any

from agent.handoffs import JobBudget, JobRequirement, JobSpec
from agent.llm import llm_call
from agent.nodes.base import NodeDeps

logger = logging.getLogger(__name__)


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> JobSpec:
    """Analyzes a job posting and emits a structured JobSpec hand-off."""
    raw_job = state_slice.get("job") or {}
    if hasattr(raw_job, "model_dump"):
        job = raw_job.model_dump()
    elif isinstance(raw_job, dict):
        job = raw_job
    else:
        job = {"description": str(raw_job)}

    persona = state_slice.get("persona") or "general_freelancer"
    title = job.get("title", "Untitled Job")
    description = job.get("description", "")
    skills = job.get("skills", [])
    budget_val = job.get("budget", 0.0)
    budget_type = job.get("budget_type", "fixed" if budget_val and budget_val > 100 else "hourly")

    job_text = f"Title: {title}\nDescription:\n{description}\nSkills: {', '.join(skills)}\nBudget: {budget_val} ({budget_type})"

    try:
        spec = llm_call(
            node="analyst",
            variables={
                "job_post": job_text,
                "persona": str(persona),
            },
            schema=JobSpec,
            model_override=deps.llm,
        )
        if isinstance(spec, JobSpec):
            return spec
    except Exception as exc:  # noqa: BLE001
        logger.debug("[analyst] LLM call failed, falling back to heuristics: %s", exc)

    # Heuristic fallback if LLM call is unavailable or fails
    reqs: list[JobRequirement] = []
    lines = [line.strip() for line in description.splitlines() if len(line.strip()) > 20]
    for i, line in enumerate(lines[:5]):
        reqs.append(JobRequirement(id=f"req_{i+1:02d}", text=line, kind="must_have"))

    return JobSpec(
        title=title,
        summary=description[:300] if len(description) > 300 else description,
        deliverables=[r.text for r in reqs[:3]],
        requirements=reqs,
        skills=skills,
        budget=JobBudget(
            type=budget_type if budget_type in {"fixed", "hourly"} else "unspecified",
            min=float(budget_val * 0.8) if budget_val else None,
            max=float(budget_val) if budget_val else None,
        ),
        screening_questions=job.get("screening_questions", []),
        hidden_needs=["Production deployment", "Testing & Documentation"],
    )
