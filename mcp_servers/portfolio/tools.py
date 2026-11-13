"""Portfolio MCP Tools: search_evidence, get_case_study, list_skills.

Strict annotations:
- readOnlyHint=True
- idempotentHint=True
- destructiveHint=False
- openWorldHint=False
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.portfolio.schemas import (
    CaseStudyOutput,
    EvidenceOutputItem,
    ListSkillsOutput,
    PortfolioErrorOutput,
    SearchEvidenceOutput,
    SkillCount,
)
from rag.ingest.loaders import load_case_studies, load_profile
from rag.retriever import get_retriever

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "personas"
VALID_EVIDENCE_TYPES = {"cv", "case_study", "repo_readme", "repo_code", "review", "proposal"}
VALID_OUTCOMES = {"won", "replied", "ignored"}


def register_portfolio_tools(
    mcp: FastMCP,
    get_persona_fn: Callable[[], str],
    data_dir: Path | str | None = None,
    use_hash_embedder: bool = False,
) -> None:
    """Registers read-only portfolio exploration tools onto the FastMCP server."""
    persona_root = Path(data_dir or DEFAULT_DATA_DIR)

    portfolio_annotations = ToolAnnotations(
        readOnlyHint=True,
        idempotentHint=True,
        destructiveHint=False,
        openWorldHint=False,
    )

    # -------------------------------------------------------------------------
    # 1. search_evidence
    # -------------------------------------------------------------------------
    @mcp.tool(
        name="search_evidence",
        annotations=portfolio_annotations,
        description=(
            "Search verified portfolio evidence chunks matching a client job requirement or technical topic.\n"
            "When to use: Use when analyzing a job description or screening question to find concrete past projects, "
            "code samples, case studies, or proposal proof points backing a capability claim.\n"
            "When NOT to use: Do NOT use if you already have the specific case study ID (use get_case_study instead). "
            "Do NOT use to browse the overall skill inventory (use list_skills instead)."
        ),
    )
    async def search_evidence(
        requirement: str = Field(
            ...,
            min_length=3,
            max_length=500,
            description="Client requirement, query string, or technical capability to search for (3..500 characters)",
        ),
        k: int = Field(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of evidence items to return (1..20)",
        ),
        filters: dict[str, Any] | None = Field(  # noqa: B008
            default=None,
            description=(
                "Optional metadata filters: type in {cv, case_study, repo_readme, repo_code, review, proposal}, "
                "skills list[str], outcome in {won, replied, ignored}"
            ),
        ),
    ) -> SearchEvidenceOutput | PortfolioErrorOutput:
        active_persona = get_persona_fn()

        # Validate requirement length
        req_clean = requirement.strip()
        if len(req_clean) < 3 or len(req_clean) > 500:
            return PortfolioErrorOutput(
                error="invalid_argument",
                detail=f"Requirement length must be between 3 and 500 characters (received {len(req_clean)}).",
                persona=active_persona,
            )

        # Validate k
        if k < 1 or k > 20:
            return PortfolioErrorOutput(
                error="invalid_argument",
                detail=f"k must be between 1 and 20 (received {k}).",
                persona=active_persona,
            )

        # Validate filters if supplied
        sanitized_filters: dict[str, Any] = {"persona": active_persona}
        if filters:
            if "type" in filters:
                ftype = filters["type"]
                if ftype not in VALID_EVIDENCE_TYPES:
                    return PortfolioErrorOutput(
                        error="invalid_argument",
                        detail=f"Invalid filter type '{ftype}'. Must be one of {sorted(VALID_EVIDENCE_TYPES)}.",
                        persona=active_persona,
                    )
                sanitized_filters["type"] = ftype

            if "outcome" in filters:
                foutcome = filters["outcome"]
                if foutcome not in VALID_OUTCOMES:
                    return PortfolioErrorOutput(
                        error="invalid_argument",
                        detail=f"Invalid filter outcome '{foutcome}'. Must be one of {sorted(VALID_OUTCOMES)}.",
                        persona=active_persona,
                    )
                sanitized_filters["outcome"] = foutcome

            if "skills" in filters:
                fskills = filters["skills"]
                if isinstance(fskills, str):
                    sanitized_filters["skills"] = [fskills]
                elif isinstance(fskills, list):
                    sanitized_filters["skills"] = [str(s) for s in fskills]

        try:
            retriever = get_retriever(
                persona=active_persona,
                use_hash_embedder=use_hash_embedder,
            )
            evidence_items = await retriever.retrieve(
                query=req_clean,
                k=k,
                filters=sanitized_filters,
            )

            output_items: list[EvidenceOutputItem] = []
            for item in evidence_items:
                output_items.append(
                    EvidenceOutputItem(
                        id=item.id,
                        type=item.type,
                        source=item.source,
                        project=item.project,
                        date=item.date,
                        outcome=item.outcome,
                        text=item.text,
                        score=round(item.score, 4),
                        skills=item.skills,
                    )
                )

            return SearchEvidenceOutput(
                persona=active_persona,
                requirement=req_clean,
                count=len(output_items),
                items=output_items,
            )
        except Exception as exc:  # noqa: BLE001
            return PortfolioErrorOutput(
                error="retrieval_error",
                detail=f"Failed to execute evidence search: {exc}",
                persona=active_persona,
            )

    # -------------------------------------------------------------------------
    # 2. get_case_study
    # -------------------------------------------------------------------------
    @mcp.tool(
        name="get_case_study",
        annotations=portfolio_annotations,
        description=(
            "Retrieve full Markdown text and verified metadata for a specific case study by ID.\n"
            "When to use: Use when a client job requires deep proof of a particular past project, "
            "or when citing a case study referenced in search_evidence.\n"
            "When NOT to use: Do NOT use to search across all case studies (use search_evidence instead)."
        ),
    )
    def get_case_study(
        id: str = Field(..., description="Unique case study ID (e.g. cs_01 or cs_01.md)"),
    ) -> CaseStudyOutput | PortfolioErrorOutput:
        active_persona = get_persona_fn()
        persona_dir = persona_root / active_persona

        if not persona_dir.is_dir():
            return PortfolioErrorOutput(
                error="persona_not_found",
                detail=f"Persona directory '{active_persona}' does not exist.",
                persona=active_persona,
            )

        cs_id_target = id.removesuffix(".md").strip()
        all_cases = load_case_studies(persona_dir)

        # Match exact ID, normalized ID, filename stem, or numeric suffix
        matched_case: dict[str, Any] | None = None
        digits_target = "".join(filter(str.isdigit, cs_id_target))
        for cs in all_cases:
            cs_id = cs["id"].removesuffix(".md")
            if (
                cs["id"] == cs_id_target
                or cs_id == cs_id_target
                or f"cs_{cs_id_target}" == cs["id"]
                or cs["id"] == f"cs_{cs_id_target}"
                or cs["id"] == f"{active_persona}_{cs_id_target}"
                or (digits_target and "".join(filter(str.isdigit, cs_id)).lstrip("0") == digits_target.lstrip("0"))
            ):
                matched_case = cs
                break

        if not matched_case:
            return PortfolioErrorOutput(
                error="not_found",
                detail=f"Case study '{id}' not found for persona '{active_persona}'.",
                persona=active_persona,
            )

        return CaseStudyOutput(
            id=matched_case["id"],
            persona=active_persona,
            project=matched_case.get("project", matched_case["id"]),
            skills=matched_case.get("skills", []),
            date=matched_case.get("date"),
            client_industry=matched_case.get("client_industry"),
            outcome=matched_case.get("outcome"),
            text=matched_case.get("text", ""),
            source_path=matched_case.get("source_path", ""),
        )

    # -------------------------------------------------------------------------
    # 3. list_skills
    # -------------------------------------------------------------------------
    @mcp.tool(
        name="list_skills",
        annotations=portfolio_annotations,
        description=(
            "List all technical and domain skills claimed across the persona's verified artifacts, "
            "with counts of how many evidence items back each skill.\n"
            "When to use: Use during the scouting and qualification phase to check if a persona possesses "
            "the must-have skills requested by a client.\n"
            "When NOT to use: Do NOT use to fetch detailed proof of a project (use get_case_study or search_evidence)."
        ),
    )
    def list_skills() -> ListSkillsOutput | PortfolioErrorOutput:
        active_persona = get_persona_fn()
        persona_dir = persona_root / active_persona

        if not persona_dir.is_dir():
            return PortfolioErrorOutput(
                error="persona_not_found",
                detail=f"Persona directory '{active_persona}' does not exist.",
                persona=active_persona,
            )

        skill_counter: Counter[str] = Counter()

        # Count from profile
        profile = load_profile(persona_dir)
        for s in profile.get("skills", []):
            skill_counter[str(s).strip()] += 1

        # Count from case studies
        for cs in load_case_studies(persona_dir):
            for s in cs.get("skills", []):
                skill_counter[str(s).strip()] += 1

        # Check cached chunks file if available for broader counts (proposals, repos)
        index_dir = persona_root.parent / "processed" / "index"
        chunks_cache = index_dir / f"{active_persona}_chunks.jsonl"
        if chunks_cache.is_file():
            import json

            try:
                for line in chunks_cache.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    c_data = json.loads(line)
                    for s in c_data.get("skills", []):
                        if s:
                            skill_counter[str(s).strip()] += 1
            except (json.JSONDecodeError, OSError):
                pass

        if not skill_counter:
            return ListSkillsOutput(persona=active_persona, skills=[], total_skills=0)

        # Sort descending by count, then alphabetically
        sorted_skills = sorted(
            [SkillCount(skill=s, count=c) for s, c in skill_counter.items() if s],
            key=lambda x: (-x.count, x.skill.lower()),
        )

        return ListSkillsOutput(
            persona=active_persona,
            skills=sorted_skills,
            total_skills=len(sorted_skills),
        )
