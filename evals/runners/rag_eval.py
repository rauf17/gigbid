"""Retrieval Evaluation Runner (AI-4016 Assignment B4).

CLI:
    uv run python -m evals.runners.rag_eval --variant v0_naive [--persona X] [--limit N] [--smoke]

Metrics:
    - Recall@5: Fraction of relevant gold evidence chunks retrieved in top 5.
    - MRR (Mean Reciprocal Rank): 1 / rank of first relevant item in top 10.
    - nDCG@10: Normalized Discounted Cumulative Gain at rank 10 with binary relevance.
    - Latency (p50, p95): Elapsed retrieval time in milliseconds.
    - Resources: LLM token count and estimated cost in USD.

Slices:
    - Overall: Across all evaluated jobs.
    - By persona: ai_ml, fullstack, data_analyst.
    - By n_requirements: 1-2, 3-4, 5+.

Outputs:
    - evals/results/rag_<variant>_<timestamp>.json
    - evals/results/rag_<variant>_latest.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

if "LLM_CACHE" not in os.environ:
    os.environ["LLM_CACHE"] = "1"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_PERSONAS = ["ai_ml", "fullstack", "data_analyst"]
DEFAULT_CALL_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "llm_calls.jsonl"

ALL_KNOWN_REPOS = {
    "llm-guardrails",
    "rag-eval-pipeline",
    "realtime-ops-dashboard",
    "saas-subscription-core",
    "dbt-analytics-warehouse",
    "kpi-executive-dashboard",
}


class FakeDecomposeChatModel:
    """Hermetic deterministic fake chat model for smoke testing without network/API calls."""

    model_name: str = "fake-decompose-model"

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        from langchain_core.messages import AIMessage

        content = json.dumps(
            {
                "requirements": [
                    "FastAPI REST endpoints and pydantic schema validation",
                    "PostgreSQL database design and query optimization",
                    "Docker containerized microservices and deployment",
                ]
            }
        )
        return AIMessage(content=content)


class StubCrossEncoder:
    """Deterministic stub cross-encoder for fast offline smoke testing."""

    def predict(self, pairs: list[tuple[str, str]], **kwargs: Any) -> list[float]:
        return [float(len(pairs) - idx) for idx in range(len(pairs))]


def read_new_llm_metrics(log_path: Path, start_offset: int) -> tuple[int, float, int]:
    """Reads newly logged LLM calls since start_offset.

    Returns:
        (total_tokens, total_cost_usd, new_offset)
    """
    if not log_path.is_file():
        return 0, 0.0, start_offset

    new_tokens = 0
    new_cost = 0.0
    with open(log_path, "r", encoding="utf-8") as f:
        f.seek(start_offset)
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    new_tokens += int(entry.get("prompt_tokens", 0)) + int(entry.get("completion_tokens", 0))
                    new_cost += float(entry.get("estimated_cost_usd", 0.0))
                except (json.JSONDecodeError, ValueError):
                    pass
        new_offset = f.tell()
    return new_tokens, new_cost, new_offset


def roll_up_to_item_id(chunk_id: str) -> str:
    """Rolls up fine-grained chunk IDs to item/project-level IDs.

    - CV: {persona}_cv_xxx -> {persona}_cv
    - Repo: {persona}_repo_{repo_name}_xxx -> {persona}_repo_{repo_name}
    - Case study: {persona}_cs_{id} (already item-level)
    - Review: {persona}_review_{id} (already item-level)
    - Proposal: {persona}_prop_{id} (already item-level)
    """
    m_cv = re.match(r"^([a-z_]+_cv)_\d+$", chunk_id)
    if m_cv:
        return m_cv.group(1)

    for rname in ALL_KNOWN_REPOS:
        prefix = f"_repo_{rname}"
        if prefix in chunk_id:
            persona = chunk_id.split(prefix)[0]
            return f"{persona}{prefix}"

    m_repo = re.match(r"^([a-z_]+_repo_[a-zA-Z0-9\-]+?)_(?:readme|[a-zA-Z0-9_]+)_\d+$", chunk_id)
    if m_repo:
        return m_repo.group(1)

    return chunk_id


def roll_up_retrieved_ids(chunk_ids: list[str]) -> list[str]:
    """Rolls chunk results up to item/project IDs, deduplicating while preserving best rank."""
    seen: set[str] = set()
    rolled_up: list[str] = []
    for cid in chunk_ids:
        item_id = roll_up_to_item_id(cid)
        if item_id not in seen:
            seen.add(item_id)
            rolled_up.append(item_id)
    return rolled_up


def compute_recall_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 5) -> float:
    """Computes Recall@k: fraction of gold relevant items retrieved in top-k."""
    if not gold_ids or not retrieved_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for rid in top_k if rid in gold_ids)
    return float(hits / len(gold_ids))


def compute_mrr(retrieved_ids: list[str], gold_ids: set[str], k: int = 10) -> float:
    """Computes Reciprocal Rank (RR): 1 / rank of first relevant item in top-k."""
    if not gold_ids or not retrieved_ids:
        return 0.0
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in gold_ids:
            return float(1.0 / rank)
    return 0.0


def compute_ndcg_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 10) -> float:
    """Computes Normalized Discounted Cumulative Gain at k (nDCG@k) with binary relevance."""
    if not gold_ids or not retrieved_ids:
        return 0.0

    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in gold_ids:
            dcg += 1.0 / np.log2(i + 1)

    ideal_hits = min(len(gold_ids), k)
    if ideal_hits == 0:
        return 0.0

    idcg = sum(1.0 / np.log2(i + 1) for i in range(1, ideal_hits + 1))
    return float(dcg / idcg)


def get_n_req_slice(n_req: int) -> str:
    """Categorizes requirements count into 1-2, 3-4, or 5+."""
    if n_req <= 2:
        return "1-2"
    elif n_req <= 4:
        return "3-4"
    else:
        return "5+"


def aggregate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes mean metrics, percentiles, and resource totals for evaluation records."""
    if not records:
        return {
            "count": 0,
            "recall_at_5": 0.0,
            "recall_at_5_ceiling": 0.0,
            "mrr": 0.0,
            "ndcg_at_10": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
        }
    count = len(records)
    mean_r5 = float(np.mean([r["recall_at_5"] for r in records]))
    mean_r5_ceiling = float(np.mean([r.get("recall_at_5_ceiling", 0.0) for r in records]))
    mean_mrr = float(np.mean([r["mrr"] for r in records]))
    mean_ndcg = float(np.mean([r["ndcg_at_10"] for r in records]))

    latencies = [float(r.get("latency_ms", 0.0)) for r in records]
    p50_lat = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
    total_tokens = sum(int(r.get("tokens", 0)) for r in records)
    total_cost = sum(float(r.get("cost_usd", 0.0)) for r in records)

    return {
        "count": count,
        "recall_at_5": round(mean_r5, 4),
        "recall_at_5_ceiling": round(mean_r5_ceiling, 4),
        "mrr": round(mean_mrr, 4),
        "ndcg_at_10": round(mean_ndcg, 4),
        "latency_p50_ms": round(p50_lat, 2),
        "latency_p95_ms": round(p95_lat, 2),
        "total_tokens": int(total_tokens),
        "total_cost_usd": round(total_cost, 6),
    }


def compute_dataset_hash(paths: list[Path]) -> str:
    """Computes combined SHA-256 hash across evaluated dev set files."""
    hasher = hashlib.sha256()
    for p in sorted(paths):
        if p.is_file():
            hasher.update(p.read_bytes())
    return hasher.hexdigest()[:16]


def get_git_commit() -> str:
    """Retrieves current git commit hash."""
    try:
        res = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return res.decode("utf-8").strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


async def evaluate_dev_set(
    variant: str | list[str],
    personas: list[str],
    data_dir: Path,
    limit: int | None = None,
    use_hash_embedder: bool = False,
    vector_store: Any | None = None,
    smoke: bool = False,
) -> tuple[dict[str, Any], list[Path]]:
    """Runs evaluation on dev set jobs using specified retriever variant."""
    from rag.index.bm25 import BM25Index
    from rag.retriever import get_retriever

    all_records: list[dict[str, Any]] = []
    evaluated_paths: list[Path] = []

    if isinstance(variant, list):
        canonical_variant = "_".join(variant)
        stages_arg: str | list[str] = variant
    else:
        canonical_variant = variant
        stages_arg = variant
        if variant in {"bm25_skills", "skill_tag_lookup_REFERENCE"}:
            canonical_variant = "skill_tag_lookup_REFERENCE"

    # Shared index for lexical/oracle baselines
    bm25_index: BM25Index | None = None
    if canonical_variant in {"skill_tag_lookup_REFERENCE", "bm25_text", "oracle"}:
        bm25_index = BM25Index()

    # Preload item texts for oracle baseline
    item_texts_map: dict[str, list[str]] = {}
    if canonical_variant == "oracle":
        for p in personas:
            chunks_file = data_dir.parent.parent / "data" / "processed" / "index" / f"{p}_chunks.jsonl"
            if chunks_file.is_file():
                for line in chunks_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        c = json.loads(line)
                        iid = roll_up_to_item_id(c["id"])
                        if iid not in item_texts_map:
                            item_texts_map[iid] = []
                        item_texts_map[iid].append(c["text"])

    call_log_path = DEFAULT_CALL_LOG_PATH
    log_offset = call_log_path.stat().st_size if call_log_path.is_file() else 0

    for persona in personas:
        dev_file = data_dir / f"dev_{persona}.jsonl"
        if not dev_file.is_file():
            print(f"[rag_eval] WARNING: Dev set file not found: {dev_file}")
            continue

        evaluated_paths.append(dev_file)
        lines = [line.strip() for line in dev_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if limit and limit > 0:
            lines = lines[:limit]

        # Candidate items for random baseline (35 experience items: case studies, repos, reviews, cv)
        candidate_items: list[str] = []
        rng = random.Random(42 + sum(ord(c) for c in persona))
        if canonical_variant == "random":
            chunks_file = data_dir.parent.parent / "data" / "processed" / "index" / f"{persona}_chunks.jsonl"
            if chunks_file.is_file():
                raw_chunks = [
                    json.loads(line)
                    for line in chunks_file.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                candidate_items = sorted(
                    {roll_up_to_item_id(c["id"]) for c in raw_chunks if c.get("type") != "proposal"}
                )

        retriever = None
        if canonical_variant not in {"random", "bm25_text", "skill_tag_lookup_REFERENCE", "oracle"}:
            kwargs: dict[str, Any] = {
                "persona": persona,
                "use_hash_embedder": use_hash_embedder,
                "vector_store": vector_store,
            }
            if smoke:
                kwargs["model_override"] = FakeDecomposeChatModel()
                kwargs["cross_encoder"] = StubCrossEncoder()

            retriever = get_retriever(
                variant=stages_arg,
                **kwargs,
            )

        print(f"[rag_eval] Evaluating {len(lines)} jobs for persona '{persona}' using variant '{canonical_variant}'...")
        t_start = time.time()

        for idx, line in enumerate(lines):
            row = json.loads(line)
            job = row["job"]
            gold = row["gold"]

            query = f"{job.get('title', '')}\n\n{job.get('description', '')}".strip()
            gold_ids = set(gold.get("relevant_evidence_ids", []))
            if not gold_ids:
                # Exclude empty-gold jobs from retrieval metrics (they are evaluated in decision eval)
                continue
            n_req = int(gold.get("n_requirements", 0))

            t0 = time.perf_counter()

            if canonical_variant == "random":
                retrieved_ids = rng.sample(candidate_items, min(10, len(candidate_items)))
            elif canonical_variant == "bm25_text":
                assert bm25_index is not None
                hits = bm25_index.search(
                    query=query,
                    k=35,
                    persona=persona,
                    chunk_type=["case_study", "repo_readme", "repo_code", "review", "cv"],
                )
                retrieved_ids = roll_up_retrieved_ids([c.id for c, _ in hits])[:10]
            elif canonical_variant == "skill_tag_lookup_REFERENCE":
                assert bm25_index is not None
                skill_query = " ".join(job.get("skills", []))
                hits = bm25_index.search(
                    query=skill_query,
                    k=35,
                    persona=persona,
                    chunk_type=["case_study", "repo_readme", "repo_code", "review", "cv"],
                )
                retrieved_ids = roll_up_retrieved_ids([c.id for c, _ in hits])[:10]
            elif canonical_variant == "oracle":
                assert bm25_index is not None
                gold_item_ids = gold.get("relevant_evidence_ids", [])
                raw_chunk_ids: list[str] = []
                for gid in gold_item_ids:
                    texts = item_texts_map.get(gid, [])
                    if texts:
                        hits = bm25_index.search(query=texts[0][:200], k=2, persona=persona)
                        for c, _ in hits:
                            raw_chunk_ids.append(c.id)
                retrieved_ids = roll_up_retrieved_ids(raw_chunk_ids)[:10]
            else:
                assert retriever is not None
                items = await retriever.retrieve(query=query, k=15, filters={"persona": persona})
                retrieved_ids = roll_up_retrieved_ids([item.id for item in items])[:10]

            latency_ms = (time.perf_counter() - t0) * 1000.0
            query_tokens, query_cost, log_offset = read_new_llm_metrics(call_log_path, log_offset)

            r5 = compute_recall_at_k(retrieved_ids, gold_ids, k=5)
            r5_ceiling = float(min(5, len(gold_ids)) / len(gold_ids))
            mrr = compute_mrr(retrieved_ids, gold_ids, k=10)
            ndcg = compute_ndcg_at_k(retrieved_ids, gold_ids, k=10)

            all_records.append(
                {
                    "job_id": job.get("id"),
                    "persona": persona,
                    "n_requirements": n_req,
                    "n_req_slice": get_n_req_slice(n_req),
                    "recall_at_5": r5,
                    "recall_at_5_ceiling": r5_ceiling,
                    "mrr": mrr,
                    "ndcg_at_10": ndcg,
                    "latency_ms": round(latency_ms, 2),
                    "tokens": int(query_tokens),
                    "cost_usd": round(query_cost, 6),
                }
            )

            if (idx + 1) % 50 == 0 or (idx + 1) == len(lines):
                elapsed = time.time() - t_start
                print(f"  Processed {idx + 1}/{len(lines)} jobs ({elapsed:.1f}s)")

        if retriever and hasattr(retriever, "close"):
            retriever.close()

    # Slices aggregation
    overall = aggregate_metrics(all_records)

    by_persona: dict[str, Any] = {}
    for persona in personas:
        p_records = [r for r in all_records if r["persona"] == persona]
        by_persona[persona] = aggregate_metrics(p_records)

    by_n_requirements: dict[str, Any] = {}
    for n_slice in ("1-2", "3-4", "5+"):
        s_records = [r for r in all_records if r["n_req_slice"] == n_slice]
        by_n_requirements[n_slice] = aggregate_metrics(s_records)

    results = {
        "overall": overall,
        "by_persona": by_persona,
        "by_n_requirements": by_n_requirements,
    }
    return results, evaluated_paths


def run_rag_eval(
    variant: str,
    persona: str | None = None,
    limit: int | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    use_hash_embedder: bool = False,
    smoke: bool = False,
) -> dict[str, Any]:
    """Executes evaluation and writes result JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    personas = [persona] if persona else DEFAULT_PERSONAS

    is_hash = smoke or use_hash_embedder or os.getenv("USE_HASH_EMBEDDER") == "1"
    effective_limit = limit
    if smoke and effective_limit is None:
        effective_limit = 10 if len(personas) > 1 else 30

    canonical_variant = variant
    if variant in {"bm25_skills", "skill_tag_lookup_REFERENCE"}:
        canonical_variant = "skill_tag_lookup_REFERENCE"

    results, evaluated_paths = asyncio.run(
        evaluate_dev_set(
            variant=canonical_variant,
            personas=personas,
            data_dir=data_dir,
            limit=effective_limit,
            use_hash_embedder=is_hash,
            smoke=smoke,
        )
    )

    dataset_hash = compute_dataset_hash(evaluated_paths)
    git_commit = get_git_commit()
    timestamp = datetime.now(UTC).isoformat()
    timestamp_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    output_payload: dict[str, Any] = {
        "variant": canonical_variant,
        "timestamp": timestamp,
        "git_commit": git_commit,
        "dataset_hash": dataset_hash,
        "config": {
            "variant": canonical_variant,
            "k": 10,
            "embedder": "none"
            if canonical_variant in {"random", "bm25_text", "skill_tag_lookup_REFERENCE", "oracle"}
            else ("HashEmbedder" if is_hash else "BAAI/bge-small-en-v1.5"),
            "dimension": 0
            if canonical_variant in {"random", "bm25_text", "skill_tag_lookup_REFERENCE", "oracle"}
            else (64 if is_hash else 384),
            "personas": personas,
            "limit": effective_limit,
            "smoke": smoke,
        },
        "overall": results["overall"],
        "by_persona": results["by_persona"],
        "by_n_requirements": results["by_n_requirements"],
    }

    if canonical_variant == "skill_tag_lookup_REFERENCE":
        output_payload["is_reference_only"] = True
        output_payload["note"] = (
            "queries the skills field the gold labels were derived from; "
            "leaks the answer key; reference only."
        )

    # Write timestamped file
    ts_file = output_dir / f"rag_{canonical_variant}_{timestamp_slug}.json"
    ts_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    # Update stable latest file
    latest_file = output_dir / f"rag_{canonical_variant}_latest.json"
    latest_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print("\n[rag_eval] Results saved to:")
    print(f"  {ts_file}")
    print(f"  {latest_file}")
    print("\nSummary Metrics:")
    print(
        f"  Overall: Count={results['overall']['count']}, "
        f"Recall@5={results['overall']['recall_at_5']:.4f} "
        f"(Ceiling={results['overall']['recall_at_5_ceiling']:.4f}), "
        f"MRR={results['overall']['mrr']:.4f}, nDCG@10={results['overall']['ndcg_at_10']:.4f}, "
        f"p95_lat={results['overall']['latency_p95_ms']:.1f}ms, "
        f"Tokens={results['overall']['total_tokens']}, "
        f"USD=${results['overall']['total_cost_usd']:.4f}"
    )

    return output_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG retrieval evaluation on synthetic dev set.")
    parser.add_argument("--variant", type=str, default="v0_naive", help="RAG variant (e.g. v0_naive)")
    parser.add_argument("--persona", type=str, default=None, help="Target persona (ai_ml, fullstack, data_analyst)")
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to evaluate per persona")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory containing dev sets")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for result JSONs")
    parser.add_argument(
        "--use-hash-embedder",
        action="store_true",
        help="Use deterministic HashEmbedder for fast offline testing",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run 30 dev jobs with HashEmbedder and FakeLLM in <5s",
    )
    args = parser.parse_args()

    run_rag_eval(
        variant=args.variant,
        persona=args.persona,
        limit=args.limit,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        use_hash_embedder=args.use_hash_embedder,
        smoke=args.smoke,
    )


if __name__ == "__main__":
    main()
