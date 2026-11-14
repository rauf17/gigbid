"""Decomposition stage extracting atomic technical requirements via LLM call."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from agent.llm import llm_call

logger = logging.getLogger(__name__)


class DecomposedRequirements(BaseModel):
    """Schema for decomposed job requirements."""

    requirements: list[str] = Field(
        ...,
        min_length=2,
        max_length=8,
        description="2 to 8 atomic technical requirements extracted from the job posting.",
    )


class DecomposeStage:
    """Decomposes a complex job post into 2-8 distinct atomic technical requirements."""

    def __init__(self, model_override: Any | None = None) -> None:
        self.model_override = model_override

    def execute(
        self,
        query: str,
        job_title: str | None = None,
        job_description: str | None = None,
    ) -> list[str]:
        title = job_title or (query.split("\n\n")[0] if "\n\n" in query else query[:100])
        desc = job_description or (query.split("\n\n", 1)[1] if "\n\n" in query else query)

        try:
            parsed = llm_call(
                node="requirement_decomposer",
                variables={
                    "job_title": title,
                    "job_description": desc,
                },
                schema=DecomposedRequirements,
                model_override=self.model_override,
            )
            if isinstance(parsed, DecomposedRequirements) and parsed.requirements:
                return parsed.requirements[:8]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[decompose] LLM decomposition call failed: %s. Falling back to query split.", exc)

        # Fallback heuristic: split lines or sentences if LLM call is unavailable
        lines = [line.strip() for line in desc.splitlines() if len(line.strip()) > 15]
        if len(lines) >= 2:
            return lines[:6]

        return [query]
