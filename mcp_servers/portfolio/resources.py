"""Portfolio MCP Resource Templates: portfolio://case/{id} and portfolio://proposal/{id}."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rag.ingest.loaders import load_case_studies, load_proposals

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "personas"


def register_portfolio_resources(
    mcp: FastMCP,
    get_persona_fn: Callable[[], str],
    data_dir: Path | str | None = None,
) -> None:
    """Registers MCP resource templates for direct URI browsing."""
    persona_root = Path(data_dir or DEFAULT_DATA_DIR)

    @mcp.resource(
        "portfolio://case/{id}",
        description="Returns the full Markdown text and front-matter of a specific case study.",
        mime_type="text/markdown",
    )
    def case_study_resource(id: str) -> str:
        active_persona = get_persona_fn()
        persona_dir = persona_root / active_persona

        if not persona_dir.is_dir():
            raise ValueError(f"Persona '{active_persona}' not found")

        cs_id_target = id.removesuffix(".md").strip()
        all_cases = load_case_studies(persona_dir)
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
                source_path = Path(cs["source_path"])
                if source_path.is_file():
                    return source_path.read_text(encoding="utf-8")
                return f"# Case Study: {cs['project']}\n\n{cs['text']}"

        raise ValueError(f"Case study '{id}' not found for persona '{active_persona}'")

    @mcp.resource(
        "portfolio://proposal/{id}",
        description="Returns historical proposal cover letter text and outcome status.",
        mime_type="text/markdown",
    )
    def proposal_resource(id: str) -> str:
        active_persona = get_persona_fn()
        persona_dir = persona_root / active_persona

        if not persona_dir.is_dir():
            raise ValueError(f"Persona '{active_persona}' not found")

        prop_id_target = id.strip()
        all_proposals = load_proposals(persona_dir)
        prop_digits = "".join(filter(str.isdigit, prop_id_target))

        for p in all_proposals:
            pid = str(p.get("id", ""))
            pid_digits = "".join(filter(str.isdigit, pid))
            if (
                pid == prop_id_target
                or f"prop_{prop_id_target}" == pid
                or pid == f"prop_{prop_id_target}"
                or (prop_digits and pid_digits.lstrip("0") == prop_digits.lstrip("0"))
            ):
                return (
                    f"# Proposal {pid}\n\n"
                    f"- **Job Title**: {p.get('job_title', 'N/A')}\n"
                    f"- **Category**: {p.get('category', 'N/A')}\n"
                    f"- **Outcome**: {p.get('outcome', 'unknown')}\n"
                    f"- **Date**: {p.get('date', 'N/A')}\n\n"
                    f"## Cover Letter Text\n\n{p.get('text', '')}\n"
                )

        raise ValueError(f"Proposal '{id}' not found for persona '{active_persona}'")
