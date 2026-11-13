"""Pydantic schemas for Portfolio MCP Server tools, resources, and error handling."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvidenceOutputItem(BaseModel):
    """Normalized evidence item returned by portfolio search tools."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique evidence chunk identifier")
    type: str = Field(..., description="Evidence type (cv, case_study, repo_readme, repo_code, review, proposal)")
    source: str = Field(..., description="Relative file path or origin of the chunk")
    project: str | None = Field(default=None, description="Associated project or client initiative")
    date: str | None = Field(default=None, description="ISO date or approximate timeframe")
    outcome: str | None = Field(default=None, description="Proposal outcome if applicable (won, replied, ignored)")
    text: str = Field(..., description="Body excerpt of the evidence")
    score: float = Field(..., description="Relevance score (cosine similarity or hybrid score)")
    skills: list[str] = Field(default_factory=list, description="Extracted skills evidenced by this chunk")


class SearchEvidenceOutput(BaseModel):
    """Output envelope for search_evidence tool."""

    model_config = ConfigDict(extra="ignore")

    persona: str = Field(..., description="Freelancer persona whose portfolio was queried")
    requirement: str = Field(..., description="Input requirement or query string")
    count: int = Field(..., description="Number of evidence items returned")
    items: list[EvidenceOutputItem] = Field(default_factory=list, description="Top matching evidence items")


class CaseStudyOutput(BaseModel):
    """Full detail view of a single project case study."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Case study identifier (e.g. cs_01)")
    persona: str = Field(..., description="Persona who authored the case study")
    project: str = Field(..., description="Title of the project or engagement")
    skills: list[str] = Field(default_factory=list, description="Skills exercised in this project")
    date: str | None = Field(default=None, description="Completion date")
    client_industry: str | None = Field(default=None, description="Client industry sector")
    outcome: str | None = Field(default=None, description="Key measurable outcomes or impact")
    text: str = Field(..., description="Full markdown narrative of the case study")
    source_path: str = Field(..., description="Path to source markdown file")


class SkillCount(BaseModel):
    """Skill name and total evidence count backing it."""

    model_config = ConfigDict(extra="ignore")

    skill: str = Field(..., description="Canonical skill name")
    count: int = Field(..., description="Number of evidence items mentioning or demonstrating this skill")


class ListSkillsOutput(BaseModel):
    """Aggregated skill inventory across all persona portfolio artifacts."""

    model_config = ConfigDict(extra="ignore")

    persona: str = Field(..., description="Active freelancer persona")
    skills: list[SkillCount] = Field(default_factory=list, description="Deduplicated skill list sorted by backing evidence count")
    total_skills: int = Field(..., description="Total number of unique skills identified")


class PortfolioErrorOutput(BaseModel):
    """Structured error payload for failed tool calls."""

    model_config = ConfigDict(extra="ignore")

    error: str = Field(..., description="Error category code (not_found, invalid_argument, persona_not_found)")
    detail: str = Field(..., description="Human-readable explanation of the error")
    persona: str | None = Field(default=None, description="Persona context during the failure")
