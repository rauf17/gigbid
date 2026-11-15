"""Budget measurement runner (Prompt 14 Part 4).

Executes 20 jobs end-to-end with caches cleared (LLM_CACHE=0).
Measures p50/p95 latency and tokens/USD per job analysed and per proposal.
Writes results to evals/results/budget_latest.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from agent.llm import DEFAULT_CALL_LOG_PATH, load_config
from agent.nodes import (
    analyst,
    compliance,
    critic,
    decision,
    fit_matcher,
    pricing,
    risk_assessor,
    verifier,
    writer,
)
from agent.nodes.base import NodeDeps
from rag.retriever import get_retriever

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        return res.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


async def measure_single_job(
    job_row: dict[str, Any],
    persona: str,
    node_deps: NodeDeps,
) -> dict[str, Any]:
    """Runs a single job end-to-end and measures analysis vs proposal timing and token usage."""
    job = job_row["job"]
    call_log_path = DEFAULT_CALL_LOG_PATH
    initial_log_offset = call_log_path.stat().st_size if call_log_path.is_file() else 0

    # Phase 1: Job Analysed
    t0_analysis = time.perf_counter()
    spec = await analyst.run({"job": job, "persona": persona}, node_deps)
    risk_rep = await risk_assessor.run({"job": job, "client_history": job.get("client_history")}, node_deps)
    fit_rep = await fit_matcher.run({"job_spec": spec, "persona": persona, "job": job}, node_deps)
    dec = await decision.run({"job_spec": spec, "risk_report": risk_rep, "fit_report": fit_rep, "job": job}, node_deps)
    await pricing.run({"job": job, "job_spec": spec, "risk_report": risk_rep, "fit_report": fit_rep}, node_deps)
    t1_analysis = time.perf_counter()
    analysis_latency_s = t1_analysis - t0_analysis

    # Extract LLM logs for analysis phase
    analysis_tokens = 0
    analysis_cost = 0.0
    if call_log_path.is_file():
        with call_log_path.open("r", encoding="utf-8") as f:
            f.seek(initial_log_offset)
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    analysis_tokens += int(entry.get("prompt_tokens", 0)) + int(entry.get("completion_tokens", 0))
                    analysis_cost += float(entry.get("estimated_cost_usd", 0.0))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed parsing analysis log line: %s", exc)

    proposal_evaluated = False
    proposal_latency_s = 0.0
    proposal_tokens = 0
    proposal_cost = 0.0

    # Phase 2: Proposal (run if decision == "bid" or gold says bid to measure proposal phase)
    if dec.action == "bid" or job_row.get("gold", {}).get("bid_or_skip") == "bid":
        proposal_evaluated = True
        log_offset_prop = call_log_path.stat().st_size if call_log_path.is_file() else 0
        t0_prop = time.perf_counter()

        evidence_items = []
        if node_deps.retriever:
            try:
                evidence_items = await node_deps.retriever.retrieve(
                    query=job.get("description", "")[:300],
                    k=8,
                    filters={"persona": persona},
                )
            except Exception:  # noqa: BLE001
                evidence_items = []

        draft = await writer.run(
            {
                "job": job,
                "job_spec": spec,
                "fit_report": fit_rep,
                "persona": persona,
                "evidence_items": evidence_items,
            },
            node_deps,
        )
        ver_rep = await verifier.run(
            {"draft": draft, "evidence_items": evidence_items, "persona": persona},
            node_deps,
        )
        await critic.run(
            {"draft": draft, "job": job, "job_spec": spec, "fit_report": fit_rep, "verification_report": ver_rep},
            node_deps,
        )
        await compliance.run(
            {"draft": draft, "job": job, "fit_report": fit_rep, "verification_report": ver_rep},
            node_deps,
        )
        t1_prop = time.perf_counter()
        proposal_latency_s = t1_prop - t0_prop

        if call_log_path.is_file():
            with call_log_path.open("r", encoding="utf-8") as f:
                f.seek(log_offset_prop)
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        proposal_tokens += int(entry.get("prompt_tokens", 0)) + int(entry.get("completion_tokens", 0))
                        proposal_cost += float(entry.get("estimated_cost_usd", 0.0))
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Failed parsing proposal log line: %s", exc)

    return {
        "job_id": job["id"],
        "persona": persona,
        "decision": dec.action,
        "analysis_latency_s": round(analysis_latency_s, 3),
        "analysis_tokens": analysis_tokens,
        "analysis_cost_usd": round(analysis_cost, 6),
        "proposal_evaluated": proposal_evaluated,
        "proposal_latency_s": round(proposal_latency_s, 3) if proposal_evaluated else None,
        "proposal_tokens": proposal_tokens if proposal_evaluated else None,
        "proposal_cost_usd": round(proposal_cost, 6) if proposal_evaluated else None,
    }


async def run_budget_benchmark(
    n_jobs: int = 20,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    smoke: bool = False,
) -> dict[str, Any]:
    """Runs n_jobs end to end with LLM_CACHE=0 and computes budget statistics."""
    os.environ["LLM_CACHE"] = "0"
    start_ts = datetime.now(UTC).isoformat()
    commit_sha = get_git_commit()

    personas = ["ai_ml", "data_analyst", "fullstack"]
    rows: list[tuple[dict[str, Any], str]] = []

    # Distribute 20 jobs across personas
    per_persona = math.ceil(n_jobs / len(personas))
    for p in personas:
        dev_file = data_dir / f"dev_{p}.jsonl"
        if dev_file.is_file():
            lines = [json.loads(l) for l in dev_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            for item in lines[:per_persona]:
                rows.append((item, p))

    rows = rows[:n_jobs]
    print(f"[budget_measure] Running {len(rows)} jobs end-to-end with LLM_CACHE=0 (smoke={smoke})...")

    llm_override = None
    if smoke:
        from evals.runners.proposal_eval import FakeProposalChatModel

        llm_override = FakeProposalChatModel()

    retriever = get_retriever(use_hash_embedder=smoke)
    node_deps = NodeDeps(llm=llm_override, retriever=retriever)

    measurements = []
    try:
        for idx, (job_row, p) in enumerate(rows, start=1):
            print(f"[{idx}/{len(rows)}] Measuring job {job_row['job']['id']} ({p})...")
            m = await measure_single_job(job_row, p, node_deps)
            measurements.append(m)
    finally:
        try:
            if hasattr(retriever, "vector_store") and hasattr(retriever.vector_store, "client"):
                retriever.vector_store.client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed closing retriever: %s", exc)

    # Compute p50/p95 and aggregates
    analysis_lats = [m["analysis_latency_s"] for m in measurements]
    analysis_tokens = [m["analysis_tokens"] for m in measurements]
    analysis_costs = [m["analysis_cost_usd"] for m in measurements]

    prop_recs = [m for m in measurements if m["proposal_evaluated"]]
    prop_lats = [m["proposal_latency_s"] for m in prop_recs if m["proposal_latency_s"] is not None]
    prop_tokens = [m["proposal_tokens"] for m in prop_recs if m["proposal_tokens"] is not None]
    prop_costs = [m["proposal_cost_usd"] for m in prop_recs if m["proposal_cost_usd"] is not None]

    an_p50 = float(np.percentile(analysis_lats, 50)) if analysis_lats else 0.0
    an_p95 = float(np.percentile(analysis_lats, 95)) if analysis_lats else 0.0
    an_mean_tokens = float(np.mean(analysis_tokens)) if analysis_tokens else 0.0
    an_mean_cost = float(np.mean(analysis_costs)) if analysis_costs else 0.0

    pr_p50 = float(np.percentile(prop_lats, 50)) if prop_lats else 0.0
    pr_p95 = float(np.percentile(prop_lats, 95)) if prop_lats else 0.0
    pr_mean_tokens = float(np.mean(prop_tokens)) if prop_tokens else 0.0
    pr_mean_cost = float(np.mean(prop_costs)) if prop_costs else 0.0

    # Load declared targets from config.yaml
    cfg = load_config()
    declared_budgets = cfg.get("budgets", {})
    declared_p95 = declared_budgets.get("declared_p95_latency_s", {"job_analysed": 12.0, "proposal": 25.0})
    declared_cost = declared_budgets.get("declared_cost_usd", {"job_analysed": 0.01, "proposal": 0.03})

    report = {
        "benchmark_name": "declared_budget_measurement",
        "description": "End-to-end latency and cost accounting with caches cleared (LLM_CACHE=0)",
        "timestamp": datetime.now(UTC).isoformat(),
        "start_time": start_ts,
        "commit_sha": commit_sha,
        "llm_mode": "fake" if smoke else "real",
        "jobs_evaluated": len(measurements),
        "proposals_evaluated": len(prop_recs),
        "job_analysed": {
            "p50_latency_s": round(an_p50, 3),
            "p95_latency_s": round(an_p95, 3),
            "mean_tokens": round(an_mean_tokens, 1),
            "mean_cost_usd": round(an_mean_cost, 6),
            "declared_target_p95_s": float(declared_p95.get("job_analysed", 12.0)),
            "declared_target_cost_usd": float(declared_cost.get("job_analysed", 0.01)),
            "within_p95_budget": bool(an_p95 <= float(declared_p95.get("job_analysed", 12.0))),
            "within_cost_budget": bool(an_mean_cost <= float(declared_cost.get("job_analysed", 0.01))),
        },
        "proposal": {
            "p50_latency_s": round(pr_p50, 3),
            "p95_latency_s": round(pr_p95, 3),
            "mean_tokens": round(pr_mean_tokens, 1),
            "mean_cost_usd": round(pr_mean_cost, 6),
            "declared_target_p95_s": float(declared_p95.get("proposal", 25.0)),
            "declared_target_cost_usd": float(declared_cost.get("proposal", 0.03)),
            "within_p95_budget": bool(pr_p95 <= float(declared_p95.get("proposal", 25.0))),
            "within_cost_budget": bool(pr_mean_cost <= float(declared_cost.get("proposal", 0.03))),
        },
        "measurements": measurements,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_file = output_dir / f"budget_{ts_slug}.json"
    latest_file = output_dir / "budget_latest.json"

    run_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[budget_measure] Wrote benchmark report to {latest_file}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Declared Budget")
    parser.add_argument("--n", type=int, default=20, help="Number of jobs to measure")
    parser.add_argument("--smoke", action="store_true", help="Run with smoke/fake model")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Datasets directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Results directory")
    args = parser.parse_args()

    asyncio.run(
        run_budget_benchmark(
            n_jobs=args.n,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            smoke=args.smoke,
        )
    )


if __name__ == "__main__":
    main()
