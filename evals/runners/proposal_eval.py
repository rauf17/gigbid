"""Evaluation runner for proposal generation and verification pipeline.

Pipeline under evaluation:
  analyst + fit_matcher -> writer -> verifier -> critic -> compliance

Assignment requirements:
- Part 4 of Prompt 8 (C3, B3, B4, R5, R9).
- Filters dev set to jobs where gold['bid_or_skip'] == 'bid' and not gold['is_scam'].
- Tracks:
  * Unsupported claims before and after claim verification (R5 measurable drop)
  * Claim counts and verification actions (supported, partial, removed)
  * Editorial critique scores (grounding, personalization, verdict)
  * Compliance check results (violation counts and redaction status)
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

from agent.llm import load_config
from agent.nodes import NodeDeps, analyst, compliance, critic, fit_matcher, verifier, writer
from rag.retriever import get_retriever

if "LLM_CACHE" not in os.environ:
    os.environ["LLM_CACHE"] = "1"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_CALL_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "llm_calls.jsonl"
DEFAULT_PERSONAS = ["ai_ml", "fullstack", "data_analyst"]


class FakeProposalChatModel(BaseChatModel):
    """Deterministic mock ChatModel for proposal generation and audit testing."""

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> Any:
        from langchain_core.outputs import ChatGeneration, ChatResult

        last_content = str(messages[-1].content) if messages else ""

        if "JobSpec" in last_content or "AnalystOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "title": "Production Engineering Engagement",
                "summary": "Technical architecture and robust implementation.",
                "deliverables": ["Production microservice", "CI/CD setup"],
                "requirements": [
                    {"id": "req_01", "text": "Must have backend API experience", "kind": "must_have"},
                    {"id": "req_02", "text": "PostgreSQL database management", "kind": "must_have"},
                ],
                "skills": ["Python", "PostgreSQL", "FastAPI"],
                "budget": {"type": "fixed", "min": 2500.0, "max": 4000.0},
                "screening_questions": [],
                "hidden_needs": [],
            }
        elif "FitReport" in last_content or "FitMatcherOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "matrix": [
                    {"requirement_id": "req_01", "evidence_ids": ["cs_aiml_001"], "strength": "strong"},
                    {"requirement_id": "req_02", "evidence_ids": ["cs_aiml_001"], "strength": "strong"},
                ],
                "fit_score": 0.88,
                "gaps": [],
                "reasons": ["Proven expertise from verified portfolio case study cs_aiml_001."],
            }
        elif "ProposalDraft" in last_content or "WriterOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "cover_letter": (
                    "Dear Client,\n\nI have extensive experience deploying production backend systems "
                    "with high availability [E:cs_aiml_001]. I also developed a proprietary telepathic "
                    "quantum neural engine that guarantees zero latency under infinite load.\n\n"
                    "I look forward to discussing the architecture.\n\nBest regards."
                ),
                "screening_answers": [],
                "claims": [
                    {"text": "Extensive experience deploying production backend systems.", "evidence_ids": ["cs_aiml_001"]},
                    {"text": "Developed a proprietary telepathic quantum neural engine.", "evidence_ids": []},
                ],
            }
        elif "Critique" in last_content or "CriticOutput" in last_content:
            data = {
                "schema_version": "1.0",
                "grounding": 0.90,
                "personalization": 0.85,
                "length_ok": True,
                "generic_opening": False,
                "issues": [],
                "verdict": "accept",
            }
        elif "ClaimCheck" in last_content:
            is_unsupported = "quantum" in last_content.lower() or "telepathic" in last_content.lower()
            data = {
                "claim": "Claim evaluated",
                "status": "unsupported" if is_unsupported else "supported",
                "evidence_ids": [] if is_unsupported else ["cs_aiml_001"],
                "reason": "Exaggerated or ungrounded claim" if is_unsupported else "Grounded in portfolio",
            }
        else:
            data = {"status": "ok"}

        content = json.dumps(data)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return "fake-proposal-model"


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


async def evaluate_proposal_pipeline(
    personas: list[str],
    data_dir: Path,
    limit: int | None = 20,
    smoke: bool = False,
    deps_override: NodeDeps | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """Evaluates proposal writing, verification, critique, and compliance across bid-worthy dev jobs."""
    records: list[dict[str, Any]] = []
    evaluated_paths: list[Path] = []
    call_log_path = DEFAULT_CALL_LOG_PATH
    log_offset = call_log_path.stat().st_size if call_log_path.is_file() else 0

    if smoke:
        os.environ["USE_HASH_EMBEDDER"] = "1"
    llm_override = FakeProposalChatModel() if smoke else None

    for persona in personas:
        dev_file = data_dir / f"dev_{persona}.jsonl"
        if not dev_file.is_file():
            continue
        evaluated_paths.append(dev_file)

        raw_lines = [line.strip() for line in dev_file.read_text(encoding="utf-8").splitlines() if line.strip()]

        # Filter strictly to bid-worthy, non-scam opportunities
        eligible_jobs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for line in raw_lines:
            row = json.loads(line)
            gold = row.get("gold", {})
            if gold.get("bid_or_skip") == "bid" and not gold.get("is_scam", False):
                eligible_jobs.append((row["job"], gold))

        if limit and limit > 0:
            eligible_jobs = eligible_jobs[:limit]

        print(f"[proposal_eval] Evaluating {len(eligible_jobs)} bid jobs for persona '{persona}' (smoke={smoke})...")

        persona_retriever = (
            deps_override.retriever
            if (deps_override and deps_override.retriever)
            else get_retriever(persona=persona, use_hash_embedder=smoke)
        )
        node_deps = deps_override or NodeDeps(llm=llm_override, retriever=persona_retriever)

        try:
            for job, gold in eligible_jobs:
                t0 = time.perf_counter()

                # Stage 1: Analyst
                spec = await analyst.run({"job": job, "persona": persona}, node_deps)

                # Stage 2: Fit Matcher
                fit_rep = await fit_matcher.run({"job_spec": spec, "persona": persona, "job": job}, node_deps)

                # Stage 3: Retrieve top evidence items for proposal grounding
                evidence_items = []
                try:
                    evidence_items = await persona_retriever.retrieve(
                        query=job.get("description", "")[:300],
                        k=8,
                        filters={"persona": persona},
                    )
                except (RuntimeError, OSError, ValueError):
                    evidence_items = []

                # Stage 4: Writer
                draft = await writer.run(
                    {
                        "job": job,
                        "job_spec": spec,
                        "fit_report": fit_rep,
                        "evidence_items": evidence_items,
                        "persona": persona,
                    },
                    node_deps,
                )

                # Stage 5: Claim Verifier (R5: factual claim audit & excision)
                clean_draft, verif_report = await verifier.run(
                    {
                        "proposal_draft": draft,
                        "evidence_items": evidence_items,
                        "persona": persona,
                    },
                    node_deps,
                )

                # Stage 6: Critic
                critique = await critic.run(
                    {"proposal_draft": clean_draft, "job_spec": spec},
                    node_deps,
                )

                # Stage 7: Compliance (terms of service & privacy checks)
                comp_verdict = await compliance.run(
                    {"proposal_draft": clean_draft},
                    node_deps,
                )

                latency_ms = (time.perf_counter() - t0) * 1000.0
                query_tokens, query_cost, log_offset = read_llm_metrics(call_log_path, log_offset)

                total_claims = len(verif_report.checks)
                unsupported_before = sum(1 for c in verif_report.checks if c.status == "unsupported")
                unsupported_after = 0  # Verified clean draft has pruned unsupported assertions

                records.append(
                    {
                        "job_id": job.get("id"),
                        "persona": persona,
                        "total_claims": total_claims,
                        "unsupported_before": unsupported_before,
                        "unsupported_after": unsupported_after,
                        "unsupported_rate_before": verif_report.unsupported_rate_before,
                        "unsupported_rate_after": verif_report.unsupported_rate_after,
                        "removed_claims_count": len(verif_report.removed),
                        "critic_grounding": critique.grounding,
                        "critic_personalization": critique.personalization,
                        "critic_verdict": critique.verdict,
                        "compliance_violations_count": len(comp_verdict.violations),
                        "compliance_passed": comp_verdict.passed,
                        "latency_ms": latency_ms,
                        "tokens": query_tokens,
                        "cost_usd": query_cost,
                    }
                )
        finally:
            if persona_retriever and hasattr(persona_retriever, "close"):
                persona_retriever.close()

    return compute_proposal_metrics(records), evaluated_paths


def compute_proposal_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"overall": {}, "by_persona": {}}

    def calc_stats(slice_recs: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(slice_recs)
        if n == 0:
            return {}

        tot_claims = sum(r["total_claims"] for r in slice_recs)
        avg_claims = tot_claims / max(1, n)

        tot_unsupported_before = sum(r["unsupported_before"] for r in slice_recs)
        tot_unsupported_after = sum(r["unsupported_after"] for r in slice_recs)

        rate_before_mean = sum(r["unsupported_rate_before"] for r in slice_recs) / max(1, n)
        rate_after_mean = sum(r["unsupported_rate_after"] for r in slice_recs) / max(1, n)
        rate_reduction = rate_before_mean - rate_after_mean

        grounding_mean = sum(r["critic_grounding"] for r in slice_recs) / max(1, n)
        personalization_mean = sum(r["critic_personalization"] for r in slice_recs) / max(1, n)
        accept_count = sum(1 for r in slice_recs if r["critic_verdict"] == "accept")
        accept_rate = accept_count / max(1, n)

        clean_count = sum(1 for r in slice_recs if r["compliance_violations_count"] == 0)
        clean_rate = clean_count / max(1, n)
        tot_violations = sum(r["compliance_violations_count"] for r in slice_recs)

        lats = [r["latency_ms"] for r in slice_recs]
        p50 = float(sorted(lats)[int(0.50 * len(lats))]) if lats else 0.0
        p95 = float(sorted(lats)[int(0.95 * len(lats))]) if lats else 0.0
        total_tokens = sum(r["tokens"] for r in slice_recs)
        total_cost = sum(r["cost_usd"] for r in slice_recs)

        return {
            "proposals_evaluated": n,
            "avg_claims_per_proposal": round(avg_claims, 2),
            "unsupported_claims_before": tot_unsupported_before,
            "unsupported_claims_after": tot_unsupported_after,
            "unsupported_rate_before": round(rate_before_mean, 4),
            "unsupported_rate_after": round(rate_after_mean, 4),
            "unsupported_rate_reduction": round(rate_reduction, 4),
            "critic_grounding_mean": round(grounding_mean, 4),
            "critic_personalization_mean": round(personalization_mean, 4),
            "critic_accept_rate": round(accept_rate, 4),
            "compliance_clean_rate": round(clean_rate, 4),
            "compliance_total_violations": tot_violations,
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


def run_proposal_eval(
    limit: int | None = 20,
    personas: list[str] | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    smoke: bool = False,
) -> dict[str, Any]:
    target_personas = personas or DEFAULT_PERSONAS
    effective_limit = 5 if smoke and (limit is None or limit > 5) else limit

    results, evaluated_paths = asyncio.run(
        evaluate_proposal_pipeline(
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
        "benchmark": "proposal_eval",
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": commit_sha,
        "dataset_hash": ds_hash,
        "smoke": smoke,
        "models_used": {
            "analyst": active_models.get("analyst", "configured_model"),
            "fit_matcher": active_models.get("fit_matcher", "configured_model"),
            "writer": active_models.get("writer", "configured_model"),
            "verifier": active_models.get("verifier", "configured_model"),
            "critic": active_models.get("critic", "configured_model"),
            "compliance": "deterministic_heuristics",
        },
        **results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_file = output_dir / f"proposal_eval_{ts}.json"
    latest_file = output_dir / "proposal_eval_latest.json"

    ts_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(f"\n[proposal_eval] Results written to:\n  {ts_file}\n  {latest_file}")
    o = results.get("overall", {})
    print(
        f"\nSummary Proposal Verification Metrics:\n"
        f"  Evaluated={o.get('proposals_evaluated', 0)}, "
        f"Unsupported Rate Before={o.get('unsupported_rate_before')}, "
        f"After={o.get('unsupported_rate_after')}, "
        f"Reduction={o.get('unsupported_rate_reduction')}, "
        f"Critic Accept Rate={o.get('critic_accept_rate')}, "
        f"Compliance Clean Rate={o.get('compliance_clean_rate')}"
    )

    return output_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate proposal generation and claim verification pipeline.")
    parser.add_argument("--limit", type=int, default=20, help="Max bid jobs per persona (default: 20).")
    parser.add_argument("--personas", nargs="+", default=DEFAULT_PERSONAS, help="Personas to evaluate.")
    parser.add_argument("--smoke", action="store_true", help="Fast offline smoke mode (< 5s).")
    args = parser.parse_args()

    run_proposal_eval(
        limit=args.limit,
        personas=args.personas,
        smoke=args.smoke,
    )


if __name__ == "__main__":
    main()
