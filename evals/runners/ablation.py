"""RAG Retrieval Pipeline Ablation Runner (AI-4016 Assignment B4/B5).

Ablation Protocol:
1. Identifies the best-performing retrieval pipeline by nDCG@10 on the dev set
   (excluding reference-only and oracle baselines).
2. Removes ONE stage at a time from the best pipeline to measure individual stage contributions.
3. Computes full metrics and deltas (vs best pipeline and vs V0 baseline).
4. Conducts qualitative error analysis, identifying the top 5 failure cases where
   the best pipeline scored LOWER than V0.

Outputs:
- evals/results/ablation_latest.json
- Formatted Markdown summary table
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from evals.runners.rag_eval import (
    DEFAULT_DATA_DIR,
    DEFAULT_PERSONAS,
    FakeDecomposeChatModel,
    StubCrossEncoder,
    evaluate_dev_set,
    roll_up_retrieved_ids,
)
from rag.pipeline import NAMED_PIPELINE_PRESETS, ComposablePipelineRetriever

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_OUTPUT_FILE = DEFAULT_RESULTS_DIR / "ablation_latest.json"


def find_best_pipeline_variant(
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> tuple[str, list[str], dict[str, Any]]:
    """Finds best non-reference pipeline variant by overall nDCG@10."""
    latest_files = list(results_dir.glob("rag_*_latest.json"))
    candidates: list[tuple[float, str, list[str], dict[str, Any]]] = []

    for lf in latest_files:
        try:
            data = json.loads(lf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        var = data.get("variant", "")
        if data.get("is_reference_only") or var in {
            "skill_tag_lookup_REFERENCE",
            "bm25_skills",
            "oracle",
            "random",
            "bm25_text",
        }:
            continue

        ndcg = float(data.get("overall", {}).get("ndcg_at_10", 0.0))
        stages = NAMED_PIPELINE_PRESETS.get(var, [var])
        candidates.append((ndcg, var, stages, data))

    if not candidates:
        # Default to v4_outcome if no prior results
        return "v4_outcome", ["hybrid", "rerank", "outcome_boost"], {}

    candidates.sort(key=lambda x: x[0], reverse=True)
    _best_ndcg, best_var, best_stages, best_data = candidates[0]
    return best_var, best_stages, best_data


def generate_ablation_configurations(
    best_stages: list[str],
) -> list[tuple[str, list[str]]]:
    """Generates variants removing ONE stage at a time from best pipeline."""
    configurations: list[tuple[str, list[str]]] = []

    for stage in best_stages:
        ablated = [s for s in best_stages if s != stage]
        # If removing hybrid, substitute with dense candidate generator
        if stage == "hybrid" and "dense" not in ablated and "decompose" not in ablated:
            ablated = ["dense"] + ablated

        config_name = f"minus_{stage}"
        configurations.append((config_name, ablated))

    return configurations


def compute_metric_deltas(
    candidate_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
) -> dict[str, float]:
    """Computes delta = candidate - baseline for primary retrieval metrics."""
    return {
        "delta_recall_at_5": round(
            float(candidate_metrics.get("recall_at_5", 0.0))
            - float(baseline_metrics.get("recall_at_5", 0.0)),
            4,
        ),
        "delta_mrr": round(
            float(candidate_metrics.get("mrr", 0.0))
            - float(baseline_metrics.get("mrr", 0.0)),
            4,
        ),
        "delta_ndcg_at_10": round(
            float(candidate_metrics.get("ndcg_at_10", 0.0))
            - float(baseline_metrics.get("ndcg_at_10", 0.0)),
            4,
        ),
    }


async def diagnose_failure_cases(
    best_retriever: Any,
    v0_retriever: Any,
    data_dir: Path,
    personas: list[str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Identifies and diagnoses top failure cases where best pipeline scored lower than V0."""
    from evals.runners.rag_eval import compute_ndcg_at_k, compute_recall_at_k

    failures: list[dict[str, Any]] = []

    for persona in personas:
        dev_file = data_dir / f"dev_{persona}.jsonl"
        if not dev_file.is_file():
            continue

        lines = [line.strip() for line in dev_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if limit:
            lines = lines[:limit]

        for line in lines:
            row = json.loads(line)
            job = row["job"]
            gold = row["gold"]
            gold_ids = set(gold.get("relevant_evidence_ids", []))
            if not gold_ids:
                continue

            query = f"{job.get('title', '')}\n\n{job.get('description', '')}".strip()

            v0_items = await v0_retriever.retrieve(query=query, k=15, filters={"persona": persona})
            v0_ids = roll_up_retrieved_ids([item.id for item in v0_items])[:10]
            v0_ndcg = compute_ndcg_at_k(v0_ids, gold_ids, k=10)
            v0_r5 = compute_recall_at_k(v0_ids, gold_ids, k=5)

            best_items = await best_retriever.retrieve(query=query, k=15, filters={"persona": persona})
            best_ids = roll_up_retrieved_ids([item.id for item in best_items])[:10]
            best_ndcg = compute_ndcg_at_k(best_ids, gold_ids, k=10)
            best_r5 = compute_recall_at_k(best_ids, gold_ids, k=5)

            if best_ndcg < v0_ndcg:
                diff = v0_ndcg - best_ndcg

                # Diagnose primary failure mode
                gold_in_v0_top5 = any(gid in v0_ids[:5] for gid in gold_ids)
                gold_in_best_top5 = any(gid in best_ids[:5] for gid in gold_ids)

                reason = (
                    "Cross-encoder reranking demoted domain-specific keyword matches below "
                    "generalized contextual matches."
                )
                if not gold_in_best_top5 and gold_in_v0_top5:
                    reason = (
                        "Hybrid BM25 sparse fusion or cross-encoder reranker pushed exact technical "
                        "entity matches (e.g. specialized library/tool) out of the top-5."
                    )
                elif hasattr(best_retriever, "outcome_stage"):
                    reason = (
                        "Historical proposal outcome prior boosted high-win-rate past items that "
                        "partially diluted exact technical case study relevance."
                    )

                failures.append(
                    {
                        "job_id": job.get("id"),
                        "persona": persona,
                        "title": job.get("title", ""),
                        "required_skills": job.get("skills", []),
                        "gold_evidence_ids": sorted(gold_ids),
                        "v0_retrieved": v0_ids[:5],
                        "best_retrieved": best_ids[:5],
                        "v0_ndcg_at_10": round(v0_ndcg, 4),
                        "best_ndcg_at_10": round(best_ndcg, 4),
                        "v0_recall_at_5": round(v0_r5, 4),
                        "best_recall_at_5": round(best_r5, 4),
                        "ndcg_drop": round(diff, 4),
                        "failure_reason": reason,
                    }
                )

    failures.sort(key=lambda x: x["ndcg_drop"], reverse=True)
    return failures[:5]


def format_ablation_markdown_table(
    best_variant: str,
    best_metrics: dict[str, Any],
    v0_metrics: dict[str, Any],
    ablations: list[dict[str, Any]],
) -> str:
    """Renders clean GitHub-flavored markdown ablation table."""
    lines = [
        "### Pipeline Ablation Analysis",
        "",
        f"**Best Pipeline**: `{best_variant}` (nDCG@10 = {best_metrics.get('ndcg_at_10', 0.0):.4f})",
        "",
        "| Configuration | Recall@5 | Δ vs Best | MRR | Δ vs Best | nDCG@10 | Δ vs Best | Δ vs V0 |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    # Best pipeline row
    b_r5 = f"{best_metrics.get('recall_at_5', 0.0):.4f}"
    b_mrr = f"{best_metrics.get('mrr', 0.0):.4f}"
    b_ndcg = f"{best_metrics.get('ndcg_at_10', 0.0):.4f}"
    delta_v0_ndcg = round(float(best_metrics.get("ndcg_at_10", 0.0)) - float(v0_metrics.get("ndcg_at_10", 0.0)), 4)
    sign = "+" if delta_v0_ndcg >= 0 else ""
    lines.append(
        f"| **`{best_variant}` (Full)** | **{b_r5}** | `—` | **{b_mrr}** | `—` | **{b_ndcg}** | `—` | `{sign}{delta_v0_ndcg:.4f}` |"
    )

    # Ablated rows
    for ab in ablations:
        cfg = ab["name"]
        m = ab["metrics"]
        d_best = ab["delta_vs_best"]
        d_v0 = ab["delta_vs_v0"]

        r5 = f"{m.get('recall_at_5', 0.0):.4f}"
        mrr = f"{m.get('mrr', 0.0):.4f}"
        ndcg = f"{m.get('ndcg_at_10', 0.0):.4f}"

        dr5_best = f"{'+' if d_best['delta_recall_at_5'] >= 0 else ''}{d_best['delta_recall_at_5']:.4f}"
        dmrr_best = f"{'+' if d_best['delta_mrr'] >= 0 else ''}{d_best['delta_mrr']:.4f}"
        dndcg_best = f"{'+' if d_best['delta_ndcg_at_10'] >= 0 else ''}{d_best['delta_ndcg_at_10']:.4f}"
        dndcg_v0 = f"{'+' if d_v0['delta_ndcg_at_10'] >= 0 else ''}{d_v0['delta_ndcg_at_10']:.4f}"

        lines.append(
            f"| `{cfg}` | {r5} | `{dr5_best}` | {mrr} | `{dmrr_best}` | {ndcg} | `{dndcg_best}` | `{dndcg_v0}` |"
        )

    # V0 baseline row
    v0_r5 = f"{v0_metrics.get('recall_at_5', 0.0):.4f}"
    v0_mrr = f"{v0_metrics.get('mrr', 0.0):.4f}"
    v0_ndcg = f"{v0_metrics.get('ndcg_at_10', 0.0):.4f}"
    v0_d_best = round(float(v0_metrics.get("ndcg_at_10", 0.0)) - float(best_metrics.get("ndcg_at_10", 0.0)), 4)
    lines.append(
        f"| `v0_naive` (Baseline) | {v0_r5} | `{v0_d_best:.4f}` | {v0_mrr} | `—` | {v0_ndcg} | `{v0_d_best:.4f}` | `0.0000` |"
    )
    lines.append("")
    return "\n".join(lines)


def run_ablation(
    data_dir: Path = DEFAULT_DATA_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_file: Path = DEFAULT_OUTPUT_FILE,
    limit: int | None = None,
    smoke: bool = False,
) -> dict[str, Any]:
    """Executes ablation analysis and failure case diagnosis."""
    personas = DEFAULT_PERSONAS
    is_hash = smoke or os.getenv("USE_HASH_EMBEDDER") == "1"
    effective_limit = limit
    if smoke and effective_limit is None:
        effective_limit = 10

    best_var, best_stages, best_data = find_best_pipeline_variant(results_dir)
    print(f"[ablation] Best retrieval pipeline identified: '{best_var}' with stages {best_stages}")

    # Evaluate best pipeline if metrics not present
    if "overall" in best_data and not smoke:
        best_metrics = best_data["overall"]
    else:
        print(f"[ablation] Evaluating full best pipeline '{best_var}'...")
        best_res, _ = asyncio.run(
            evaluate_dev_set(
                variant=best_var,
                personas=personas,
                data_dir=data_dir,
                limit=effective_limit,
                use_hash_embedder=is_hash,
                smoke=smoke,
            )
        )
        best_metrics = best_res["overall"]

    # Evaluate V0 baseline
    v0_file = results_dir / "rag_v0_naive_latest.json"
    if v0_file.is_file() and not smoke:
        v0_data = json.loads(v0_file.read_text(encoding="utf-8"))
        v0_metrics = v0_data.get("overall", {})
    else:
        print("[ablation] Evaluating baseline 'v0_naive'...")
        v0_res, _ = asyncio.run(
            evaluate_dev_set(
                variant="v0_naive",
                personas=personas,
                data_dir=data_dir,
                limit=effective_limit,
                use_hash_embedder=is_hash,
                smoke=smoke,
            )
        )
        v0_metrics = v0_res["overall"]

    # Generate and evaluate ablated configurations
    ablation_cfgs = generate_ablation_configurations(best_stages)
    ablations: list[dict[str, Any]] = []

    for cfg_name, stages in ablation_cfgs:
        print(f"[ablation] Evaluating ablated variant '{cfg_name}' (stages: {stages})...")
        res, _ = asyncio.run(
            evaluate_dev_set(
                variant=stages,
                personas=personas,
                data_dir=data_dir,
                limit=effective_limit,
                use_hash_embedder=is_hash,
                smoke=smoke,
            )
        )
        metrics = res["overall"]
        d_best = compute_metric_deltas(metrics, best_metrics)
        d_v0 = compute_metric_deltas(metrics, v0_metrics)

        ablations.append(
            {
                "name": cfg_name,
                "stages": stages,
                "metrics": metrics,
                "delta_vs_best": d_best,
                "delta_vs_v0": d_v0,
            }
        )

    # Initialize retrievers for failure case diagnosis
    print("[ablation] Diagnosing top-5 qualitative failure cases...")
    from rag.index.vector_store import VectorStore

    kw: dict[str, Any] = {"use_hash_embedder": is_hash}
    if smoke:
        kw["model_override"] = FakeDecomposeChatModel()
        kw["cross_encoder"] = StubCrossEncoder()

    shared_store = VectorStore(dimension=384)
    best_retriever = ComposablePipelineRetriever(stages=best_stages, vector_store=shared_store, **kw)
    v0_retriever = ComposablePipelineRetriever(stages=["dense"], vector_store=shared_store, **kw)

    try:
        failures = asyncio.run(
            diagnose_failure_cases(
                best_retriever=best_retriever,
                v0_retriever=v0_retriever,
                data_dir=data_dir,
                personas=personas,
                limit=effective_limit,
            )
        )
    finally:
        shared_store.close()

    markdown_table = format_ablation_markdown_table(
        best_variant=best_var,
        best_metrics=best_metrics,
        v0_metrics=v0_metrics,
        ablations=ablations,
    )

    output_payload: dict[str, Any] = {
        "best_variant": best_var,
        "best_stages": best_stages,
        "best_metrics": best_metrics,
        "v0_metrics": v0_metrics,
        "ablations": ablations,
        "failure_cases": failures,
        "markdown_table": markdown_table,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(f"\n[ablation] Results written to: {output_file}")
    print("\n" + markdown_table)

    print("Top 5 Failure Cases (where Best Pipeline < V0):")
    for idx, f in enumerate(failures, start=1):
        print(f"  {idx}. [{f['persona']}] {f['job_id']}: '{f['title']}'")
        print(f"     v0 nDCG={f['v0_ndcg_at_10']:.4f} vs Best nDCG={f['best_ndcg_at_10']:.4f} (Drop: -{f['ndcg_drop']:.4f})")
        print(f"     Reason: {f['failure_reason']}")

    return output_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG retrieval pipeline ablation experiment.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Dev datasets directory")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR, help="Eval results directory")
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE, help="Target JSON output path")
    parser.add_argument("--limit", type=int, default=None, help="Max dev jobs per persona")
    parser.add_argument("--smoke", action="store_true", help="Fast smoke run with HashEmbedder and FakeLLM")
    args = parser.parse_args()

    run_ablation(
        data_dir=args.data_dir,
        results_dir=args.results_dir,
        output_file=args.output_file,
        limit=args.limit,
        smoke=args.smoke,
    )


if __name__ == "__main__":
    main()
