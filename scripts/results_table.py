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


def load_json_if_exists(p: Path) -> dict[str, Any] | None:
    """Safely loads a JSON result file if it exists."""
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def format_decision_table(data: dict[str, Any] | None) -> str:
    """Renders agent decision pipeline evaluation results."""
    if not data or "overall" not in data:
        return ""
    ov = data["overall"]
    commit = str(data.get("git_commit", "unknown"))[:7]
    d_hash = str(data.get("dataset_hash", "unknown"))[:8]
    smoke_tag = " (Smoke)" if data.get("smoke") else ""
    mode = data.get("llm_mode", "fake" if data.get("smoke") else "real")
    models = ", ".join(f"{k}:{v}" for k, v in data.get("models_used", {}).items())
    real_calls = data.get("real_llm_calls_count", {})
    calls_str = ", ".join(f"{k}:{v}" for k, v in real_calls.items()) if real_calls else "0"

    lines = [
        f"### Agent Decision Pipeline Performance{smoke_tag}",
        "",
        "| Metric | Value |",
        "|:---|:---:|",
        f"| **LLM Mode** | **`{mode}`** |",
        f"| Jobs Evaluated | {ov.get('count', 0)} |",
        f"| **Bid/Skip F1 Score** | **{ov.get('bid_or_skip_f1', 0.0):.4f}** |",
        f"| Bid/Skip Precision | {ov.get('bid_or_skip_precision', 0.0):.4f} |",
        f"| Bid/Skip Recall | {ov.get('bid_or_skip_recall', 0.0):.4f} |",
        f"| Bid/Skip Accuracy | {ov.get('bid_or_skip_accuracy', 0.0):.4f} |",
        f"| Scam Detection Precision | {ov.get('scam_precision', 0.0):.4f} |",
        f"| Scam Detection Recall | {ov.get('scam_recall', 0.0):.4f} |",
        f"| **Injection Detection Rate** | **{ov.get('injection_detection_rate', 0.0):.4f}** |",
        f"| Price-in-Band Rate | {ov.get('price_in_band_rate', 0.0):.4f} |",
        f"| Latency p95 (ms) | {ov.get('latency_p95_ms', 0.0):.1f} |",
        f"| Total Tokens | {int(ov.get('total_tokens', 0)):,} |",
        f"| Total Cost (USD) | ${float(ov.get('total_cost_usd', 0.0)):.4f} |",
        f"| Non-Cache LLM Calls | `{calls_str}` |",
        f"| Models Used | `{models}` |",
        f"| Dataset SHA / Commit | `{d_hash}` / `{commit}` |",
        "",
    ]
    return "\n".join(lines)


def format_proposal_table(data: dict[str, Any] | None) -> str:
    """Renders proposal verification and claim audit evaluation results (R5)."""
    if not data or "overall" not in data:
        return ""
    ov = data["overall"]
    commit = str(data.get("git_commit", "unknown"))[:7]
    d_hash = str(data.get("dataset_hash", "unknown"))[:8]
    smoke_tag = " (Smoke)" if data.get("smoke") else ""
    mode = data.get("llm_mode", "fake" if data.get("smoke") else "real")
    models = ", ".join(f"{k}:{v}" for k, v in data.get("models_used", {}).items())
    real_calls = data.get("real_llm_calls_count", {})
    calls_str = ", ".join(f"{k}:{v}" for k, v in real_calls.items()) if real_calls else "0"

    lines = [
        f"### Proposal Claim Verification & Quality (R5){smoke_tag}",
        "",
        "| Metric | Value |",
        "|:---|:---:|",
        f"| **LLM Mode** | **`{mode}`** |",
        f"| Proposals Evaluated | {ov.get('proposals_evaluated', 0)} |",
        f"| Avg Claims per Proposal | {ov.get('avg_claims_per_proposal', 0.0):.2f} |",
        f"| Unsupported Claims Before Verification | {ov.get('unsupported_claims_before', 0)} |",
        f"| Unsupported Claims After Verification | {ov.get('unsupported_claims_after', 0)} |",
        f"| Unsupported Rate Before Verification | {ov.get('unsupported_rate_before', 0.0):.4f} |",
        f"| **Unsupported Rate After Verification** | **{ov.get('unsupported_rate_after', 0.0):.4f}** |",
        f"| **Unsupported Rate Reduction (R5 Delta)** | **{ov.get('unsupported_rate_reduction', 0.0):.4f}** |",
        f"| Critic Grounding Score (Mean) | {ov.get('critic_grounding_mean', 0.0):.4f} |",
        f"| Critic Personalization Score (Mean) | {ov.get('critic_personalization_mean', 0.0):.4f} |",
        f"| Critic Accept Rate | {ov.get('critic_accept_rate', 0.0):.4f} |",
        f"| Compliance Clean Rate | {ov.get('compliance_clean_rate', 0.0):.4f} |",
        f"| Total Compliance Violations Caught | {ov.get('compliance_total_violations', 0)} |",
        f"| Latency p95 (ms) | {ov.get('latency_p95_ms', 0.0):.1f} |",
        f"| Non-Cache LLM Calls | `{calls_str}` |",
        f"| Models Used | `{models}` |",
        f"| Dataset SHA / Commit | `{d_hash}` / `{commit}` |",
        "",
    ]
    return "\n".join(lines)


def format_injection_table(data: dict[str, Any] | None) -> str:
    """Renders prompt injection defense evaluation results (R9)."""
    if not data or "overall" not in data:
        return ""
    ov = data["overall"]
    commit = str(data.get("git_commit", "unknown"))[:7]
    d_hash = str(data.get("dataset_hash", "unknown"))[:8]
    smoke_tag = " (Smoke)" if data.get("smoke") else ""
    mode = data.get("llm_mode", "fake" if data.get("smoke") else "real")
    models = ", ".join(f"{k}:{v}" for k, v in data.get("models_used", {}).items())
    real_calls = data.get("real_llm_calls_count", {})
    calls_str = ", ".join(f"{k}:{v}" for k, v in real_calls.items()) if real_calls else "0"

    lines = [
        f"### Adversarial Prompt Injection Defense (R9){smoke_tag}",
        "",
        "| Metric | Value |",
        "|:---|:---:|",
        f"| **LLM Mode** | **`{mode}`** |",
        f"| Total Adversarial Jobs Tested | {ov.get('total_adversarial_jobs', 0)} |",
        f"| **Attack Success Rate (Without Defenses)** | **{ov.get('asr_without_defenses', 0.0):.4f}** |",
        f"| **Attack Success Rate (With Defenses)** | **{ov.get('asr_with_defenses', 0.0):.4f}** |",
        f"| **ASR Absolute Reduction** | **{ov.get('asr_reduction', 0.0):.4f}** |",
        f"| **Defense Effectiveness Rate** | **{ov.get('defense_effectiveness_rate', 0.0):.4f}** |",
        f"| Injection Flagging Rate | {ov.get('injection_detection_rate', 0.0):.4f} |",
        f"| Latency p95 (ms) | {ov.get('latency_p95_ms', 0.0):.1f} |",
        f"| Non-Cache LLM Calls | `{calls_str}` |",
        f"| Models Used | `{models}` |",
        f"| Dataset SHA / Commit | `{d_hash}` / `{commit}` |",
        "",
    ]
    return "\n".join(lines)


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
        "| Variant | Mode | Recall@5 | R@5 Ceiling | MRR | nDCG@10 | p95 Lat (ms) | Tokens | USD | Queries | Embedder | Dataset SHA | Commit |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|",
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
        mode = r.get("llm_mode", "fake" if r.get("smoke") else ("real" if var == "v1_decompose" else "deterministic"))

        is_ref = r.get("is_reference_only") or var in {"skill_tag_lookup_REFERENCE", "bm25_skills"}
        if is_ref:
            has_ref = True
            label = f"`{var}`*"
        else:
            label = f"`{var}`"

        lines.append(
            f"| {label} | `{mode}` | **{r5}** | {r5_ceil} | **{mrr}** | **{ndcg}** | "
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


def format_agent_benchmarks_summary(
    decision_data: dict[str, Any] | None,
    proposal_data: dict[str, Any] | None,
    injection_data: dict[str, Any] | None,
) -> str:
    """Renders high-level summary of agent node benchmarks with Mode column."""
    lines = [
        "### Agent Benchmarks Summary",
        "",
        "| Benchmark | Mode | Primary Metric | Primary Value | p95 Lat (ms) | Real LLM Calls | Models Used |",
        "|:---|:---:|:---|:---:|:---:|:---|:---|",
    ]
    if decision_data and "overall" in decision_data:
        ov = decision_data["overall"]
        mode = decision_data.get("llm_mode", "fake" if decision_data.get("smoke") else "real")
        models = ", ".join(f"{k}:{v}" for k, v in decision_data.get("models_used", {}).items())
        calls = decision_data.get("real_llm_calls_count", {})
        calls_str = ", ".join(f"{k}:{v}" for k, v in calls.items()) if calls else "0"
        lines.append(f"| Decision Pipeline | `{mode}` | Bid/Skip F1 | **{ov.get('bid_or_skip_f1', 0.0):.4f}** | {ov.get('latency_p95_ms', 0.0):.1f} | `{calls_str}` | `{models}` |")

    if proposal_data and "overall" in proposal_data:
        ov = proposal_data["overall"]
        mode = proposal_data.get("llm_mode", "fake" if proposal_data.get("smoke") else "real")
        models = ", ".join(f"{k}:{v}" for k, v in proposal_data.get("models_used", {}).items())
        calls = proposal_data.get("real_llm_calls_count", {})
        calls_str = ", ".join(f"{k}:{v}" for k, v in calls.items()) if calls else "0"
        lines.append(f"| Proposal Verification (R5) | `{mode}` | Post-Verify Unsupported Rate | **{ov.get('unsupported_rate_after', 0.0):.4f}** | {ov.get('latency_p95_ms', 0.0):.1f} | `{calls_str}` | `{models}` |")

    if injection_data and "overall" in injection_data:
        ov = injection_data["overall"]
        mode = injection_data.get("llm_mode", "fake" if injection_data.get("smoke") else "real")
        models = ", ".join(f"{k}:{v}" for k, v in injection_data.get("models_used", {}).items())
        calls = injection_data.get("real_llm_calls_count", {})
        calls_str = ", ".join(f"{k}:{v}" for k, v in calls.items()) if calls else "0"
        lines.append(f"| Injection Defense (R9) | `{mode}` | Defense Effectiveness Rate | **{ov.get('defense_effectiveness_rate', 0.0):.4f}** | {ov.get('latency_p95_ms', 0.0):.1f} | `{calls_str}` | `{models}` |")

    lines.append("")
    return "\n".join(lines)


def generate_results_markdown(
    results: list[dict[str, Any]],
    decision_data: dict[str, Any] | None = None,
    proposal_data: dict[str, Any] | None = None,
    injection_data: dict[str, Any] | None = None,
) -> str:
    """Generates complete Markdown document from evaluation results."""
    doc_lines = [
        "# GigBid Evaluation Results Table",
        "",
        "This document records official benchmark evaluation results for the GigBid autonomous agent platform across RAG retriever variants (V0 Naive, V1 Decompose, V2 Hybrid BM25+Dense, V3 Cross-Encoder Rerank, V4 Outcome-Aware), agent decision nodes, proposal verification (R5), and adversarial prompt injection defense (R9).",
        "",
        "> [!NOTE]",
        "> All benchmark runs evaluate against the 600-job deterministic dev evaluation set (`evals/datasets/dev_<persona>.jsonl`, 200 jobs/persona).",
        "> Metrics are automatically updated by running `make eval-all`, `make eval-nodes`, or `uv run python scripts/results_table.py`.",
        "",
        "---",
        "",
    ]

    if not results:
        doc_lines.extend(
            [
                "_No retrieval evaluation results found yet. Run `make eval-all` to execute the baseline evaluation._",
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

    if decision_data or proposal_data or injection_data:
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_agent_benchmarks_summary(decision_data, proposal_data, injection_data))

    if decision_data:
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_decision_table(decision_data))

    if proposal_data:
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_proposal_table(proposal_data))

    if injection_data:
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append(format_injection_table(injection_data))

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

    decision_data = load_json_if_exists(args.results_dir / "decision_eval_latest.json")
    proposal_data = load_json_if_exists(args.results_dir / "proposal_eval_latest.json")
    injection_data = load_json_if_exists(args.results_dir / "injection_eval_latest.json")

    md_content = generate_results_markdown(
        results,
        decision_data=decision_data,
        proposal_data=proposal_data,
        injection_data=injection_data,
    )
    args.output_doc.parent.mkdir(parents=True, exist_ok=True)
    args.output_doc.write_text(md_content, encoding="utf-8")

    print(f"[results_table] Updated: {args.output_doc}")


if __name__ == "__main__":
    main()
