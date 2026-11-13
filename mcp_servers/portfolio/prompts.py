"""Portfolio MCP Prompt Templates for screening questions and job matching."""
from __future__ import annotations

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP


def register_portfolio_prompts(
    mcp: FastMCP,
    get_persona_fn: Callable[[], str],
) -> None:
    """Registers MCP prompt templates on the FastMCP server."""

    @mcp.prompt(
        "Answer a screening question from my portfolio",
        description="Renders instructions to answer an Upwork/GigSim client screening question citing portfolio evidence IDs.",
    )
    def answer_screening_question(question: str) -> str:
        active_persona = get_persona_fn()
        return (
            f"You are an expert freelancer (Persona: {active_persona}) answering a client screening question.\n\n"
            f"Client Screening Question:\n"
            f"> {question}\n\n"
            f"Mandatory Guidelines:\n"
            f"1. Search portfolio evidence using the `search_evidence` tool with keywords from the question.\n"
            f"2. Explicitly cite verifiable evidence item IDs (e.g. [cs_01], [prop_042], [repo_readme_0]) "
            f"for every capability, technology, or accomplishment you claim.\n"
            f"3. NEVER invent, extrapolate, or hallucinate experience, clients, or technologies not present in the verified portfolio.\n"
            f"4. Structure your response concisely: direct answer first, followed by concrete metrics and the supporting evidence citation IDs."
        )

    @mcp.prompt(
        "Summarise my most relevant experience for this job",
        description="Renders instructions to identify and summarise top 3 portfolio evidence items for a given job posting.",
    )
    def summarise_relevant_experience(job_text: str) -> str:
        active_persona = get_persona_fn()
        return (
            f"You are an expert freelancer (Persona: {active_persona}) evaluating fit for a newly discovered job posting.\n\n"
            f"Target Job Description:\n"
            f"> {job_text}\n\n"
            f"Mandatory Guidelines:\n"
            f"1. Query the portfolio retriever via `search_evidence(requirement=job_text, k=5)`.\n"
            f"2. Select the top 3 most relevant evidence items that directly demonstrate the client's stated requirements.\n"
            f"3. For each selected item, output:\n"
            f"   - Evidence ID and Project Name\n"
            f"   - Overlapping technical skills\n"
            f"   - Quantifiable outcome or measurable impact achieved\n"
            f"4. Provide a 2-3 sentence proposal opener highlighting these verified proof points."
        )
