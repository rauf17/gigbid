"""Evaluation runner for agent decision pipeline: analyst -> risk -> fit -> pricing -> decision.

Assignment requirements:
- Part 4 of Prompt 8 (C3, B3, B4, R5, R9).
- Evaluates dev jobs per persona (default 60).
- Reports:
  * Bid-or-skip F1, Precision, Recall, Accuracy
  * Scam Precision & Recall
  * Injection Detection Rate (on jobs with has_injection=True)
  * Price-in-band rate (vs gold fair_price_band)
  * Resource accounting: tokens, latency p50/p95, estimated cost USD
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage

from agent.handoffs import (
    RiskFlag,
)
from agent.llm import load_config
from agent.nodes import NodeDeps, analyst, decision, fit_matcher, pricing, risk_assessor
from rag.retriever import get_retriever

if "LLM_CACHE" not in os.environ:
    os.environ["LLM_CACHE"] = "1"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_CALL_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "llm_calls.jsonl"
DEFAULT_PERSONAS = ["ai_ml", "fullstack", "data_analyst"]


class FakeNodeChatModel(BaseChatModel):
    """Deterministic mock ChatModel for hermetic offline smoke testing."""

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> Any:
        from langchain_core.outputs import ChatGeneration, ChatResult

        last_content = str(messages[-1].content) if messages else ""

        if "JobSpec" in last_content or "AnalystOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "title": "Mock Engineer Job",
                "summary": "Mock technical summary of requirements.",
                "deliverables": ["Mock Deliverable 1", "Mock Deliverable 2"],
                "requirements": [
                    {"id": "req_01", "text": "Must have Python experience", "kind": "must_have"},
                    {"id": "req_02", "text": "FastAPI and PostgreSQL", "kind": "must_have"},
                ],
                "skills": ["Python", "FastAPI"],
                "budget": {"type": "fixed", "min": 1000.0, "max": 2000.0},
                "screening_questions": [],
                "hidden_needs": [],
            }
        elif "RiskReport" in last_content or "RiskAssessorOutput" in last_content:
            is_scam = "telegram" in last_content.lower() or "whatsapp" in last_content.lower()
            is_inj = "ignore previous instructions" in last_content.lower() or "<system>" in last_content.lower()
            data = {
                "schema_version": "1.0",
                "risk_score": 0.95 if (is_scam or is_inj) else 0.15,
                "flags": (["scam", "off_platform"] if is_scam else []) + (["injection_attempt"] if is_inj else []),
                "client_quality": 0.2 if is_scam else 0.8,
                "rationale": "High risk detected" if (is_scam or is_inj) else "Standard verified client job.",
                "recommendation": "block" if (is_scam or is_inj) else "ok",
                "evidence": ["scam phrase"] if is_scam else [],
            }
        elif "FitReport" in last_content or "FitMatcherOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "matrix": [
                    {"requirement_id": "req_01", "evidence_ids": ["cs_aiml_001"], "strength": "strong"},
                    {"requirement_id": "req_02", "evidence_ids": ["cs_aiml_001"], "strength": "strong"},
                ],
                "fit_score": 0.85,
                "gaps": [],
                "reasons": ["Demonstrated strong capability in portfolio evidence."],
            }
        elif "PriceQuote" in last_content or "PricingOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "bid_amount": 1500.0,
                "band_low": 1200.0,
                "band_high": 1800.0,
                "rationale": "Standard bid calculation.",
                "connects_cost": 6,
                "worth_connects": True,
            }
        else:
            data = {"status": "ok"}

        content = json.dumps(data)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return "fake-node-model"


def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def compute_dataset_hash(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for p in sorted(paths):
        if p.is_file():
            hasher.update(p.read_bytes())
    return hasher.hexdigest()[:8]


def read_llm_metrics(log_path: Path, offset: int) -> tuple[int, float, int]:
    if not log_path.is_file():
        return 0, 0.0, offset
    tokens = 0
    cost = 0.0
    new_offset = offset
    with open(log_path, encoding="utf-8") as f:
        f.seek(offset)
        for line in f:
            if line.strip():
                try:
                    d = json.loads(line)
                    tokens += int(d.get("prompt_tokens", 0)) + int(d.get("completion_tokens", 0))
                    cost += float(d.get("estimated_cost_usd", 0.0))
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        new_offset = f.tell()
    return tokens, cost, new_offset


async def evaluate_decision_nodes(
    personas: list[str],
    data_dir: Path,
    limit: int | None = 60,
    smoke: bool = False,
    deps_override: NodeDeps | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """Evaluates analyst, risk, fit, pricing, and decision nodes across dev set jobs."""
    records: list[dict[str, Any]] = []
    evaluated_paths: list[Path] = []
    call_log_path = DEFAULT_CALL_LOG_PATH
    log_offset = call_log_path.stat().st_size if call_log_path.is_file() else 0

    if smoke:
        os.environ["USE_HASH_EMBEDDER"] = "1"
    llm_override = FakeNodeChatModel() if smoke else None

    for persona in personas:
        dev_file = data_dir / f"dev_{persona}.jsonl"
        if not dev_file.is_file():
            continue
        evaluated_paths.append(dev_file)

        lines = [line.strip() for line in dev_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if limit and limit > 0:
            lines = lines[:limit]

        print(f"[decision_eval] Evaluating {len(lines)} jobs for persona '{persona}' (smoke={smoke})...")

        persona_retriever = (
            deps_override.retriever
            if (deps_override and deps_override.retriever)
            else get_retriever(persona=persona, use_hash_embedder=smoke)
        )
        node_deps = deps_override or NodeDeps(llm=llm_override, retriever=persona_retriever)

        try:
            for line in lines:
                row = json.loads(line)
                job = row["job"]
                gold = row["gold"]

                t0 = time.perf_counter()

                # Node 1: Analyst
                spec = await analyst.run({"job": job, "persona": persona}, node_deps)

                # Node 2: Risk Assessor
                risk_rep = await risk_assessor.run({"job": job, "persona": persona}, node_deps)

                # Node 3: Fit Matcher
                fit_rep = await fit_matcher.run({"job_spec": spec, "persona": persona, "job": job}, node_deps)

                # Node 4: Pricing
                quote = await pricing.run(
                    {"job": job, "persona": persona, "fit_report": fit_rep},
                    node_deps,
                )

                # Node 5: Decision (pure function)
                bid_dec = await decision.run(
                    {
                        "fit_report": fit_rep,
                        "risk_report": risk_rep,
                        "price_quote": quote,
                        "job": job,
                    },
                    node_deps,
                )

                latency_ms = (time.perf_counter() - t0) * 1000.0
                query_tokens, query_cost, log_offset = read_llm_metrics(call_log_path, log_offset)

                # Gold labels
                gold_action = str(gold.get("bid_or_skip", "skip")).lower()
                gold_scam = bool(gold.get("is_scam", False))
                gold_injection = bool(gold.get("has_injection", False))
                gold_band = gold.get("fair_price_band") or [0.0, 0.0]

                # Predictions
                pred_action = bid_dec.action.lower()
                pred_scam = (
                    RiskFlag.SCAM in risk_rep.flags
                    or RiskFlag.OFF_PLATFORM in risk_rep.flags
                    or risk_rep.risk_score >= 0.70
                    or risk_rep.recommendation == "block"
                )
                pred_injection = RiskFlag.INJECTION_ATTEMPT in risk_rep.flags

                # Price in band check
                price_in_band = False
                if gold_band and len(gold_band) >= 2 and gold_band[1] > 0:
                    low, high = float(gold_band[0]), float(gold_band[1])
                    # Within 15% tolerance of fair band
                    price_in_band = (low * 0.85 <= quote.bid_amount <= high * 1.15)
                else:
                    price_in_band = quote.bid_amount > 0

                records.append(
                    {
                        "job_id": job.get("id"),
                        "persona": persona,
                        "gold_action": gold_action,
                        "pred_action": pred_action,
                        "gold_scam": gold_scam,
                        "pred_scam": pred_scam,
                        "gold_injection": gold_injection,
                        "pred_injection": pred_injection,
                        "gold_band": gold_band,
                        "pred_bid": quote.bid_amount,
                        "price_in_band": price_in_band,
                        "fit_score": fit_rep.fit_score,
                        "risk_score": risk_rep.risk_score,
                        "latency_ms": latency_ms,
                        "tokens": query_tokens,
                        "cost_usd": query_cost,
                    }
                )
        finally:
            if persona_retriever and hasattr(persona_retriever, "close"):
                persona_retriever.close()

    return compute_metrics(records), evaluated_paths


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"overall": {}, "by_persona": {}}

    def calc_stats(slice_recs: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(slice_recs)
        if n == 0:
            return {}

        # Bid/Skip confusion matrix
        tp = sum(1 for r in slice_recs if r["pred_action"] == "bid" and r["gold_action"] == "bid")
        fp = sum(1 for r in slice_recs if r["pred_action"] == "bid" and r["gold_action"] != "bid")
        fn = sum(1 for r in slice_recs if r["pred_action"] != "bid" and r["gold_action"] == "bid")
        tn = sum(1 for r in slice_recs if r["pred_action"] != "bid" and r["gold_action"] != "bid")

        prec = tp / max(1, tp + fp)
        rec = tp / max(1, tp + fn)
        f1 = (2 * prec * rec) / max(1e-6, prec + rec) if (prec + rec) > 0 else 0.0
        acc = (tp + tn) / max(1, n)

        # Scam detection
        scam_tp = sum(1 for r in slice_recs if r["pred_scam"] and r["gold_scam"])
        scam_fp = sum(1 for r in slice_recs if r["pred_scam"] and not r["gold_scam"])
        scam_fn = sum(1 for r in slice_recs if not r["pred_scam"] and r["gold_scam"])
        scam_prec = scam_tp / max(1, scam_tp + scam_fp)
        scam_rec = scam_tp / max(1, scam_tp + scam_fn)
        scam_f1 = (2 * scam_prec * scam_rec) / max(1e-6, scam_prec + scam_rec) if (scam_prec + scam_rec) > 0 else 0.0

        # Injection detection rate (recall on has_injection=True)
        inj_total = sum(1 for r in slice_recs if r["gold_injection"])
        inj_hits = sum(1 for r in slice_recs if r["gold_injection"] and r["pred_injection"])
        inj_detection_rate = (inj_hits / inj_total) if inj_total > 0 else 1.0

        # Price in band rate
        price_rate = sum(1 for r in slice_recs if r["price_in_band"]) / max(1, n)

        # Latency & tokens
        lats = [r["latency_ms"] for r in slice_recs]
        p50 = float(sorted(lats)[int(0.50 * len(lats))]) if lats else 0.0
        p95 = float(sorted(lats)[int(0.95 * len(lats))]) if lats else 0.0
        total_tokens = sum(r["tokens"] for r in slice_recs)
        total_cost = sum(r["cost_usd"] for r in slice_recs)

        return {
            "count": n,
            "bid_or_skip_f1": round(f1, 4),
            "bid_or_skip_precision": round(prec, 4),
            "bid_or_skip_recall": round(rec, 4),
            "bid_or_skip_accuracy": round(acc, 4),
            "scam_precision": round(scam_prec, 4),
            "scam_recall": round(scam_rec, 4),
            "scam_f1": round(scam_f1, 4),
            "injection_detection_rate": round(inj_detection_rate, 4),
            "price_in_band_rate": round(price_rate, 4),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
        }

    overall = calc_stats(records)
    by_persona = {}
    for p in DEFAULT_PERSONAS:
        p_recs = [r for r in records if r["persona"] == p]
        if p_recs:
            by_persona[p] = calc_stats(p_recs)

    return {"overall": overall, "by_persona": by_persona}


def run_decision_eval(
    limit: int | None = 60,
    personas: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    smoke: bool = False,
) -> dict[str, Any]:
    target_personas = personas or DEFAULT_PERSONAS
    effective_limit = 10 if smoke and (limit is None or limit > 10) else limit

    results, evaluated_paths = asyncio.run(
        evaluate_decision_nodes(
            personas=target_personas,
            data_dir=data_dir,
            limit=effective_limit,
            smoke=smoke,
        )
    )

    commit_sha = get_git_commit()
    ds_hash = compute_dataset_hash(evaluated_paths)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    cfg = load_config()
    profile = cfg.get("profiles", {}).get(cfg.get("active_profile", "open"), {})
    active_models = profile.get("models", {})

    output_payload = {
        "benchmark": "decision_eval",
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": commit_sha,
        "dataset_hash": ds_hash,
        "smoke": smoke,
        "models_used": {
            "analyst": active_models.get("analyst", "configured_model"),
            "risk_assessor": active_models.get("risk_assessor", "configured_model"),
            "fit_matcher": active_models.get("fit_matcher", "configured_model"),
            "pricing": "deterministic_heuristics",
            "decision": "pure_function",
        },
        **results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_file = output_dir / f"decision_eval_{ts}.json"
    latest_file = output_dir / "decision_eval_latest.json"

    ts_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(f"\n[decision_eval] Results written to:\n  {ts_file}\n  {latest_file}")
    o = results.get("overall", {})
    print(
        f"\nSummary Metrics:\n"
        f"  Jobs={o.get('count', 0)}, Bid/Skip F1={o.get('bid_or_skip_f1')}, "
        f"Scam Recall={o.get('scam_recall')}, Injection Det={o.get('injection_detection_rate')}, "
        f"Price-in-Band={o.get('price_in_band_rate')}, p95 Lat={o.get('latency_p95_ms')}ms"
    )

    return output_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agent decision pipeline on dev set.")
    parser.add_argument("--limit", type=int, default=60, help="Max jobs per persona (default: 60).")
    parser.add_argument("--personas", nargs="+", default=DEFAULT_PERSONAS, help="Personas to evaluate.")
    parser.add_argument("--smoke", action="store_true", help="Fast offline smoke mode (< 5s).")
    args = parser.parse_args()

    run_decision_eval(
        limit=args.limit,
        personas=args.personas,
        smoke=args.smoke,
    )


if __name__ == "__main__":
    main()
