"""Retriever Protocol, EvidenceItem model, and retriever factory."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "agent" / "config.yaml"


class EvidenceItem(BaseModel):
    """Normalized evidence item returned by RAG retrievers."""

    id: str = Field(..., description="Unique chunk/evidence identifier.")
    type: str = Field(..., description="Artifact category (cv, case_study, repo_code, etc.).")
    source: str = Field(..., description="Relative filesystem path or provenance source.")
    project: str | None = Field(default=None, description="Project or repository context.")
    date: str | None = Field(default=None, description="Associated timestamp or date.")
    outcome: str | None = Field(default=None, description="Historical proposal outcome (if applicable).")
    text: str = Field(..., description="Evidence text content.")
    score: float = Field(..., description="Relevance retrieval score.")
    skills: list[str] = Field(default_factory=list, description="Tagged technical skills.")


@runtime_checkable
class Retriever(Protocol):
    """Protocol defining the asynchronous retrieval interface for all RAG variants."""

    async def retrieve(
        self,
        query: str | list[str],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        """Retrieve top-k relevant evidence items matching optional metadata filters."""
        ...


def get_retriever(
    variant: str | None = None,
    config_path: Path | str | None = None,
    **kwargs: Any,
) -> Retriever:
    """Factory selecting the RAG retriever variant configured in agent/config.yaml.

    Default: v0_naive
    """
    selected_variant = variant or os.getenv("RAG_VARIANT")

    if not selected_variant:
        cfg = Path(config_path or DEFAULT_CONFIG_PATH)
        if cfg.is_file():
            try:
                data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                selected_variant = data.get("rag", {}).get("variant")
            except (yaml.YAMLError, OSError):
                selected_variant = None

    selected_variant = (selected_variant or "v0_naive").lower().strip()

    if selected_variant in {"v0", "v0_naive"}:
        from rag.variants.v0_naive import V0NaiveRetriever

        return V0NaiveRetriever(unfiltered=False, **kwargs)
    elif selected_variant in {"v0_unfiltered", "v0_naive_unfiltered"}:
        from rag.variants.v0_naive import V0NaiveRetriever

        return V0NaiveRetriever(unfiltered=True, **kwargs)
    else:
        raise ValueError(f"Unknown RAG retriever variant: '{selected_variant}'")
