"""Results Table Generator (AI-4016 Assignment B4).

Parses evals/results/*_latest.json and regenerates docs/results_table.md.
Includes latency p95, tokens, and cost accounting, and clearly labels reference-only baselines.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"
DEFAULT_OUTPUT_DOC = Path(__file__).resolve().parent.parent / "docs" / "results_table.md"

CANONICAL_ORDER = [
    "random",
    "bm25_text",
    "skill_tag_lookup_REFERENCE",
    "v0_naive",
    "v1_decompose",
    "v2_hybrid",
    "v3_rerank",
    "v4_outcome",
]


def load_latest_results(results_dir: Path) -> list[dict[str, Any]]:
    """Loads all latest evaluation result files sorted by canonical variant order."""
    if not results_dir.is_dir():
        return []

    result_files = sorted(results_dir.glob("rag_*_latest.json"))
    results = []
    for rf in result_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            results.append(data)
        except (json.JSONDecodeError, OSError) as err:
            print(f"[results_table] WARNING: Error reading {rf}: {err}")

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        var = item.get("variant", "")
        if var in CANONICAL_ORDER:
            return (CANONICAL_ORDER.index(var), var)
        return (len(CANONICAL_ORDER), var)

    results.sort(key=sort_key)
    return results


def format_overall_table(results: list[dict[str, Any]]) -> str:
    """Renders main comparison table of RAG retrieval variants."""
    lines = [
        "### Overall Retrieval Performance",
        "",
        "| Variant | Recall@5 | R@5 Ceiling | MRR | nDCG@10 | p95 Lat (ms) | Tokens | USD | Queries | Embedder | Dataset SHA | Commit |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|",
    ]
    has_ref = False
    for r in results:
        var = r.get("variant", "unknown")
        ov = r.get("overall", {})
        r5 = f"{ov.get('recall_at_5', 0.0):.4f}"
        r5_ceil = f"{ov.get('recall_at_5_ceiling', 0.0):.4f}"
        mrr = f"{ov.get('mrr', 0.0):.4f}"
        ndcg = f"{ov.get('ndcg_at_10', 0.0):.4f}"
        p95_lat = f"{ov.get('latency_p95_ms', 0.0):.1f}"
        tokens = f"{int(ov.get('total_tokens', 0)):,}"
        cost = f"${float(ov.get('total_cost_usd', 0.0)):.4f}"
        count = str(ov.get("count", 0))
        emb = r.get("config", {}).get("embedder", "bge-small-en-v1.5")
        if "/" in emb:
            emb = emb.split("/")[-1]
        d_hash = str(r.get("dataset_hash", "unknown"))[:8]
        commit = str(r.get("git_commit", "unknown"))[:7]

        is_ref = r.get("is_reference_only") or var in {"skill_tag_lookup_REFERENCE", "bm25_skills"}
        if is_ref:
            has_ref = True
            label = f"`{var}`*"
        else:
            label = f"`{var}`"

        lines.append(
            f"| {label} | **{r5}** | {r5_ceil} | **{mrr}** | **{ndcg}** | "
            f"{p95_lat} | {tokens} | {cost} | {count} | `{emb}` | `{d_hash}` | `{commit}` |"
        )
    lines.append("")
    if has_ref:
        lines.append(
            "> [!NOTE]\n"
            "> `* skill_tag_lookup_REFERENCE`: queries the skills field the gold labels were derived from; "
            "leaks the answer key; reference only (excluded from ranking and ablation)."
        )
        lines.append("")
    return "\n".join(lines)


def format_persona_table(results: list[dict[str, Any]]) -> str:
    """Renders sliced metrics breakdown by freelancer persona."""
    lines = [
        "### Performance by Freelancer Persona",
        "",
        "| Variant | Persona | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|",
    ]
    persona_labels = {
        "ai_ml": "AI/ML (Dr. Elena Rostova)",
        "fullstack": "Full-Stack Web (Marcus Vance)",
        "data_analyst": "Data Analysis (Amina Al-Mansoor)",
    }

    for r in results:
        var = r.get("variant", "unknown")
        by_p = r.get("by_persona", {})
        for p_id, p_name in persona_labels.items():
            p_data = by_p.get(p_id, {})
            r5 = f"{p_data.get('recall_at_5', 0.0):.4f}"
            r5_ceil = f"{p_data.get('recall_at_5_ceiling', 0.0):.4f}"
            mrr = f"{p_data.get('mrr', 0.0):.4f}"
            ndcg = f"{p_data.get('ndcg_at_10', 0.0):.4f}"
            count = str(p_data.get("count", 0))
            lines.append(f"| `{var}` | {p_name} | {count} | {r5} | {r5_ceil} | {mrr} | {ndcg} |")
    lines.append("")
    return "\n".join(lines)


def format_n_req_table(results: list[dict[str, Any]]) -> str:
    """Renders sliced metrics breakdown by job requirement complexity."""
    lines = [
        "### Performance by Requirement Complexity (`n_requirements`)",
        "",
        "| Variant | Requirements | Queries | Recall@5 | R@5 Ceiling | MRR | nDCG@10 |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    slices = ["1-2", "3-4", "5+"]

    for r in results:
        var = r.get("variant", "unknown")
        by_req = r.get("by_n_requirements", {})
        for s in slices:
            s_data = by_req.get(s, {})
            r5 = f"{s_data.get('recall_at_5', 0.0):.4f}"
            r5_ceil = f"{s_data.get('recall_at_5_ceiling', 0.0):.4f}"
            mrr = f"{s_data.get('mrr', 0.0):.4f}"
            ndcg = f"{s_data.get('ndcg_at_10', 0.0):.4f}"
            count = str(s_data.get("count", 0))
            lines.append(f"| `{var}` | {s} skills | {count} | {r5} | {r5_ceil} | {mrr} | {ndcg} |")
    lines.append("")
    return "\n".join(lines)


def generate_results_markdown(results: list[dict[str, Any]]) -> str:
    """Generates complete Markdown document from evaluation results."""
    doc_lines = [
        "# GigBid Evaluation Results Table",
        "",
        "This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Decompose, V2 Hybrid BM25+Dense, V3 Cross-Encoder Rerank, V4 Outcome-Aware) and baseline reference models.",
        "",
        "> [!NOTE]",
        "> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).",
        "> Metrics are automatically updated by running `make eval-all` or `uv run python scripts/results_table.py`.",
        "",
        "---",
        "",
    ]

    if not results:
        doc_lines.extend(
            [
                "_No evaluation results found yet. Run `make eval-all` to execute the baseline evaluation._",
                "",
            ]
        )
    else:
        doc_lines.append(format_overall_table(results))
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_persona_table(results))
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_n_req_table(results))

    return "\n".join(doc_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate docs/results_table.md from latest eval JSONs.")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory containing latest eval results",
    )
    parser.add_argument(
        "--output-doc",
        type=Path,
        default=DEFAULT_OUTPUT_DOC,
        help="Target Markdown file path",
    )
    args = parser.parse_args()

    results = load_latest_results(args.results_dir)
    print(f"[results_table] Found {len(results)} latest RAG result file(s).")

    md_content = generate_results_markdown(results)
    args.output_doc.parent.mkdir(parents=True, exist_ok=True)
    args.output_doc.write_text(md_content, encoding="utf-8")

    print(f"[results_table] Updated: {args.output_doc}")


if __name__ == "__main__":
    main()
