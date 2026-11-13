"""RAG common data schemas and Chunk model.

Requirement A1 / B1: Common Chunk model carrying uniform metadata across all persona artifacts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChunkType = Literal[
    "cv",
    "case_study",
    "repo_readme",
    "repo_code",
    "review",
    "proposal",
]


class Chunk(BaseModel):
    """Common Chunk model representing a chunked or atomic unit of persona evidence."""

    id: str = Field(..., description="Unique chunk identifier.")
    persona: str = Field(..., description="Persona ID: 'ai_ml', 'fullstack', or 'data_analyst'.")
    type: ChunkType = Field(..., description="Artifact category of the chunk.")
    project: str | None = Field(default=None, description="Associated project or repository name.")
    skills: list[str] = Field(default_factory=list, description="Associated technical skills.")
    date: str | None = Field(default=None, description="ISO or calendar date.")
    client_industry: str | None = Field(default=None, description="Client industry sector.")
    outcome: str | None = Field(default=None, description="Proposal outcome: 'won', 'replied', or 'ignored'.")
    source_path: str = Field(..., description="Relative filesystem path to source file.")
    text: str = Field(..., description="The chunked text content.")
    content_hash: str = Field(..., description="SHA-256 hash of the chunk text for incremental indexing.")
