"""A/B proposal strategy experiment runner (Extension X2).

Compares two proposal strategies on identical candidate bid jobs:
- Arm A: Result-first opener with cited metric.
- Arm B: Question-first opener about client's problem.

Evaluates in an offline simulation harness against GigSim through MarketplacePort.
Computes two-proportion z-tests and 95% confidence intervals for reply and hire rates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.shared.memory import create_connected_server_and_client_session
from scipy.stats import norm

from agent.handoffs import ClaimAnnotation, ProposalDraft
from agent.llm import load_config
from agent.marketplace_port import McpMarketplacePort
from agent.nodes import analyst, compliance, fit_matcher, verifier, writer
from agent.nodes.base import NodeDeps
from gigsim.app import app as gigsim_app
from gigsim.app import get_db
from gigsim.seed import get_db_connection, reset_database, seed_database
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.audit import AuditStore
from mcp_servers.marketplace.server import create_mcp_server
from rag.retriever import get_retriever

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "ab_cache"
DEFAULT_PERSONAS = ["ai_ml", "data_analyst", "fullstack"]


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        return res.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def compute_two_prop_z_test(
    count_a: int, nobs_a: int, count_b: int, nobs_b: int
) -> tuple[float, float, tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Calculates two-proportion z-test, p-value, and 95% confidence intervals."""
    if nobs_a == 0 or nobs_b == 0:
        return 0.0, 1.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)

    p_a = count_a / nobs_a
    p_b = count_b / nobs_b
    diff = p_a - p_b

    # Pooled proportion for test statistic under H0
    p_pool = (count_a + count_b) / (nobs_a + nobs_b)
    if p_pool == 0.0 or p_pool == 1.0:
        z_stat = 0.0
        p_val = 1.0
    else:
        se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / nobs_a + 1.0 / nobs_b))
        z_stat = diff / se_pool if se_pool > 0 else 0.0
        p_val = float(2.0 * (1.0 - norm.cdf(abs(z_stat))))

    # 95% Confidence interval for difference
    se_diff = math.sqrt((p_a * (1.0 - p_a) / nobs_a) + (p_b * (1.0 - p_b) / nobs_b))
    ci_diff = (diff - 1.96 * se_diff, diff + 1.96 * se_diff)

    # 95% Confidence intervals for individual proportions
    se_a = math.sqrt(p_a * (1.0 - p_a) / nobs_a)
    ci_a = (max(0.0, p_a - 1.96 * se_a), min(1.0, p_a + 1.96 * se_a))

    se_b = math.sqrt(p_b * (1.0 - p_b) / nobs_b)
    ci_b = (max(0.0, p_b - 1.96 * se_b), min(1.0, p_b + 1.96 * se_b))

    return z_stat, p_val, ci_diff, ci_a, ci_b


async def generate_draft_for_arm(
    job: dict[str, Any],
    persona: str,
    arm: str,
    node_deps: NodeDeps,
    cache_dir: Path,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Generates an evidence-grounded, verified, and compliance-checked proposal draft."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{job['id']}_{persona}_{arm}.json"

    if use_cache and cache_file.is_file():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 1. Analyst
    spec = await analyst.run({"job": job, "persona": persona}, node_deps)

    # 2. Fit Matcher
    fit_rep = await fit_matcher.run({"job_spec": spec, "persona": persona, "job": job}, node_deps)

    # 3. Retrieve evidence
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

    # 4. Writer with target strategy arm
    writer_node = "writer_arm_a" if arm == "arm_a" else "writer_arm_b"
    draft = await writer.run(
        {
            "job": job,
            "job_spec": spec,
            "fit_report": fit_rep,
            "persona": persona,
            "evidence_items": evidence_items,
            "writer_node": writer_node,
        },
        node_deps,
    )

    from evals.runners.proposal_eval import FakeProposalChatModel

    if isinstance(node_deps.llm, FakeProposalChatModel):
        if evidence_items:
            first_ev = getattr(evidence_items[0], "id", None) or (evidence_items[0].get("id") if isinstance(evidence_items[0], dict) else "cs_aiml_001")
        else:
            first_ev = "cs_aiml_001"
        if arm == "arm_a":
            draft = ProposalDraft(
                cover_letter=(
                    f"In our previous engagement [E:{first_ev}], we achieved 99.9% uptime and reduced latency by 45%. "
                    f"For this project, we can deploy the exact same production architecture."
                ),
                claims=[ClaimAnnotation(text="Achieved 99.9% uptime and reduced latency by 45%.", evidence_ids=[first_ev])],
            )
        else:
            draft = ProposalDraft(
                cover_letter=(
                    f"To ensure we architect the system properly: what is your target daily event volume and latency constraint? "
                    f"We have extensive experience deploying this stack [E:{first_ev}]."
                ),
                claims=[ClaimAnnotation(text="Extensive experience deploying this stack.", evidence_ids=[first_ev])],
            )

    # 5. Verifier
    ver_res = await verifier.run(
        {"draft": draft, "evidence_items": evidence_items, "persona": persona},
        node_deps,
    )

    # 6. Compliance
    comp_res = await compliance.run(
        {"draft": draft, "job": job, "fit_report": fit_rep, "verification_report": ver_res},
        node_deps,
    )

    final_text = comp_res.redacted_text or draft.cover_letter

    result = {
        "job_id": job["id"],
        "persona": persona,
        "arm": arm,
        "cover_letter": final_text,
        "bid_amount": float(job.get("budget_max") or 2500.0),
        "screening_answers": draft.screening_answers,
        "is_compliant": comp_res.passed,
        "compliance_violations": [v.rule_id for v in comp_res.violations],
    }

    if use_cache:
        try:
            cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except OSError:
            pass

    return result


def setup_offline_gigsim(
    db_path: Path,
    evaluated_jobs: list[dict[str, Any]],
) -> sqlite3.Connection:
    """Configures isolated offline GigSim SQLite database preloaded with evaluated jobs and clients."""
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass

    conn = get_db_connection(db_path)
    reset_database(conn)

    # Seed baseline stream jobs and clients
    root = Path(__file__).resolve().parent.parent.parent
    stream_file = root / "data" / "processed" / "jobs_stream.jsonl"
    clients_file = root / "gigsim" / "seed" / "clients.json"
    seed_database(conn, stream_jobs_file=stream_file, clients_file=clients_file, initial_release_count=20)

    # Ensure all evaluated jobs are present and released in the database
    with conn:
        for job in evaluated_jobs:
            jid = job["id"]
            cid = job.get("client_id") or f"client_{jid[:8]}"

            # Insert mock client if missing
            client_exists = conn.execute("SELECT id FROM clients WHERE id = ?", (cid,)).fetchone()
            if not client_exists:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO clients (
                        id, company, industry, country, payment_verified, total_spent,
                        hire_rate, avg_rating, jobs_posted, review_count, hidden_json
                    ) VALUES (?, ?, ?, ?, 1, 45000.0, 0.82, 4.8, 25, 18, ?)
                    """,
                    (
                        cid,
                        job.get("company", "Verified Enterprise"),
                        job.get("category", "Technology"),
                        "United States",
                        json.dumps({
                            "must_have_skills": job.get("skills", []),
                            "budget_ceiling": float(job.get("budget_max") or 5000.0),
                            "dislikes_generic_openers": True,
                            "likes_metrics": True,
                            "min_specificity": 0.5,
                        }),
                    ),
                )

            # Insert or update evaluated job to released status
            skills_json = json.dumps(job.get("skills", []))
            budget_min = float(job.get("budget_min") or 1000.0)
            budget_max = float(job.get("budget_max") or 3000.0)
            connects_cost = 8

            client_country = job.get("client_country") or "United States"
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    id, title, description, category, skills_json, budget_type,
                    budget_min, budget_max, client_country, client_id, posted_at,
                    connects_cost, synthetic, is_released, released_order
                ) VALUES (?, ?, ?, ?, ?, 'fixed', ?, ?, ?, ?, ?, ?, 0, 1, 1)
                """,
                (
                    jid,
                    job.get("title", "Project Title"),
                    job.get("description", "Job Description"),
                    job.get("category", "Technology"),
                    skills_json,
                    budget_min,
                    budget_max,
                    client_country,
                    cid,
                    datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    connects_cost,
                ),
            )

        # Ensure Connects balance is abundant for evaluation batch
        conn.execute("UPDATE meta SET value = '100000' WHERE key = 'connects_balance'")

    return conn


async def run_ab_experiment(
    n_per_persona: int = 40,
    personas: list[str] | None = None,
    simulator_only: bool = False,
    smoke: bool = False,
    use_cache: bool = True,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> dict[str, Any]:
    """Executes the proposal A/B experiment between Arm A and Arm B."""
    if not simulator_only:
        sys.exit(
            "CRITICAL: The production system strictly prohibits autonomous auto-send. "
            "To run the offline evaluation harness against GigSim, pass --simulator-only explicitly."
        )

    target_personas = personas or DEFAULT_PERSONAS
    start_time = datetime.now(UTC).isoformat()
    commit_sha = get_git_commit()

    # 1. Load candidate bid jobs per persona
    persona_jobs: dict[str, list[dict[str, Any]]] = {}
    all_evaluated_jobs: list[dict[str, Any]] = []

    for persona in target_personas:
        dev_file = data_dir / f"dev_{persona}.jsonl"
        if not dev_file.is_file():
            continue
        lines = [json.loads(l) for l in dev_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        bid_jobs = [r["job"] for r in lines if r.get("gold", {}).get("bid_or_skip") == "bid" and not r.get("gold", {}).get("is_scam", False)]
        selected = bid_jobs[:n_per_persona]
        persona_jobs[persona] = selected
        all_evaluated_jobs.extend(selected)
        print(f"[ab_experiment] Selected {len(selected)} bid jobs for persona '{persona}'")

    # 2. Generate drafts for Arm A and Arm B
    print(f"[ab_experiment] Generating verified proposal drafts (cache={use_cache}, smoke={smoke})...")
    arm_a_drafts: list[dict[str, Any]] = []
    arm_b_drafts: list[dict[str, Any]] = []

    llm_override = None
    if smoke:
        from evals.runners.proposal_eval import FakeProposalChatModel

        llm_override = FakeProposalChatModel()

    retriever = get_retriever(use_hash_embedder=smoke)
    try:
        for persona, jobs in persona_jobs.items():
            node_deps = NodeDeps(llm=llm_override, retriever=retriever)

            for job in jobs:
                da = await generate_draft_for_arm(job, persona, "arm_a", node_deps, cache_dir, use_cache=use_cache)
                db = await generate_draft_for_arm(job, persona, "arm_b", node_deps, cache_dir, use_cache=use_cache)
                arm_a_drafts.append(da)
                arm_b_drafts.append(db)
    finally:
        try:
            if hasattr(retriever, "vector_store") and hasattr(retriever.vector_store, "client"):
                retriever.vector_store.client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed closing retriever vector store client: %s", exc)

    # 3. Setup isolated GigSim simulator database
    temp_db_path = cache_dir / "sim_ab_state.db"
    sim_conn = setup_offline_gigsim(temp_db_path, all_evaluated_jobs)

    # Override get_db dependency in GigSim FastAPI app
    def override_get_db():
        c = sqlite3.connect(temp_db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    gigsim_app.dependency_overrides[get_db] = override_get_db

    # 4. Submit drafts via McpMarketplacePort through Marketplace MCP
    audit_file = cache_dir / "ab_audit.db"
    if audit_file.exists():
        try:
            audit_file.unlink()
        except OSError:
            pass
    audit_store = AuditStore(db_path=audit_file)

    os.environ["GIGSIM_TESTING"] = "1"
    os.environ["GIGSIM_FAULT_RATE"] = "0.0"
    sim_token = os.getenv("GIGSIM_API_TOKEN") or "ab-experiment-token-123"
    os.environ["GIGSIM_API_TOKEN"] = sim_token

    transport = httpx.ASGITransport(app=gigsim_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {sim_token}"},
    ) as http_client:
        adapter = GigSimAdapter(client=http_client)
        mcp, _, _, _ = create_mcp_server(adapter=adapter, audit_store=audit_store)

        async with create_connected_server_and_client_session(mcp) as session:
            port = McpMarketplacePort(in_memory_session=session)

            print(f"[ab_experiment] Submitting {len(arm_a_drafts)} Arm A proposals to GigSim...")
            for draft in arm_a_drafts:
                try:
                    prop_draft = await port.create_proposal_draft(
                        job_id=draft["job_id"],
                        cover_letter=draft["cover_letter"],
                        bid_amount=draft["bid_amount"],
                        screening_answers=draft.get("screening_answers"),
                        idempotency_key=f"ab_draft_a_{draft['job_id']}",
                    )
                    await port.submit_proposal(
                        proposal_id=prop_draft.id,
                        idempotency_key=f"ab_sub_a_{draft['job_id']}",
                    )
                    draft["proposal_id"] = prop_draft.id
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Submission failed for job %s: %s", draft['job_id'], exc)

            print(f"[ab_experiment] Submitting {len(arm_b_drafts)} Arm B proposals to GigSim...")
            for draft in arm_b_drafts:
                try:
                    prop_draft = await port.create_proposal_draft(
                        job_id=draft["job_id"],
                        cover_letter=draft["cover_letter"],
                        bid_amount=draft["bid_amount"],
                        screening_answers=draft.get("screening_answers"),
                        idempotency_key=f"ab_draft_b_{draft['job_id']}",
                    )
                    await port.submit_proposal(
                        proposal_id=prop_draft.id,
                        idempotency_key=f"ab_sub_b_{draft['job_id']}",
                    )
                    draft["proposal_id"] = prop_draft.id
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Submission failed for job %s: %s", draft['job_id'], exc)

            # Advance simulation time with /admin/tick to evaluate all submitted proposals
            print("[ab_experiment] Advancing simulation with /admin/tick...")
            for _ in range(5):
                await http_client.post("/admin/tick?n=10")

    # Clean up dependency override
    gigsim_app.dependency_overrides.pop(get_db, None)

    # 5. Extract outcomes and compute statistics
    props_rows = sim_conn.execute("SELECT id, status, client_feedback FROM proposals").fetchall()
    status_by_id = {r["id"]: r["status"] for r in props_rows}
    sim_conn.close()

    def evaluate_outcomes(drafts: list[dict[str, Any]]) -> dict[str, Any]:
        n_total = len(drafts)
        n_replies = 0
        n_hires = 0
        for d in drafts:
            pid = d.get("proposal_id")
            st = status_by_id.get(pid, "ignored")
            if st in ("replied", "interview", "hired"):
                n_replies += 1
            if st == "hired":
                n_hires += 1
        reply_rate = n_replies / max(1, n_total)
        hire_rate = n_hires / max(1, n_total)
        return {
            "total_submitted": n_total,
            "reply_count": n_replies,
            "reply_rate": round(reply_rate, 4),
            "hire_count": n_hires,
            "hire_rate": round(hire_rate, 4),
        }

    overall_a = evaluate_outcomes(arm_a_drafts)
    overall_b = evaluate_outcomes(arm_b_drafts)

    # Two-proportion z-tests
    z_reply, p_reply, ci_diff_reply, ci_a_reply, ci_b_reply = compute_two_prop_z_test(
        overall_a["reply_count"], overall_a["total_submitted"],
        overall_b["reply_count"], overall_b["total_submitted"],
    )
    z_hire, p_hire, ci_diff_hire, ci_a_hire, ci_b_hire = compute_two_prop_z_test(
        overall_a["hire_count"], overall_a["total_submitted"],
        overall_b["hire_count"], overall_b["total_submitted"],
    )

    overall_a["ci_95_reply"] = [round(ci_a_reply[0], 4), round(ci_a_reply[1], 4)]
    overall_a["ci_95_hire"] = [round(ci_a_hire[0], 4), round(ci_a_hire[1], 4)]
    overall_b["ci_95_reply"] = [round(ci_b_reply[0], 4), round(ci_b_reply[1], 4)]
    overall_b["ci_95_hire"] = [round(ci_b_hire[0], 4), round(ci_b_hire[1], 4)]

    # Breakdown by persona
    by_persona: dict[str, Any] = {}
    for p in target_personas:
        p_drafts_a = [d for d in arm_a_drafts if d["persona"] == p]
        p_drafts_b = [d for d in arm_b_drafts if d["persona"] == p]
        p_res_a = evaluate_outcomes(p_drafts_a)
        p_res_b = evaluate_outcomes(p_drafts_b)
        pz_rep, pp_rep, _pci_rep, _, _ = compute_two_prop_z_test(
            p_res_a["reply_count"], p_res_a["total_submitted"],
            p_res_b["reply_count"], p_res_b["total_submitted"],
        )
        by_persona[p] = {
            "arm_a": p_res_a,
            "arm_b": p_res_b,
            "reply_rate_diff": round(p_res_a["reply_rate"] - p_res_b["reply_rate"], 4),
            "reply_z_stat": round(pz_rep, 4),
            "reply_p_value": round(pp_rep, 4),
            "significant_05": bool(pp_rep < 0.05),
        }

    cfg = load_config()
    profile = cfg.get("profiles", {}).get(cfg.get("active_profile", "open"), {})
    models_used = {
        "analyst": profile.get("nodes", {}).get("analyst", {}).get("model", "openai/gpt-oss-20b"),
        "fit_matcher": profile.get("nodes", {}).get("fit_matcher", {}).get("model", "openai/gpt-oss-20b"),
        "writer_arm_a": profile.get("nodes", {}).get("writer_arm_a", {}).get("model", "openai/gpt-oss-120b"),
        "writer_arm_b": profile.get("nodes", {}).get("writer_arm_b", {}).get("model", "openai/gpt-oss-120b"),
        "verifier": profile.get("nodes", {}).get("verifier", {}).get("model", "openai/gpt-oss-120b"),
        "compliance": "deterministic_heuristics",
    }

    experiment_report = {
        "experiment_name": "extension_x2_proposal_strategies",
        "description": "A/B experiment comparing result-first opener (Arm A) vs question-first opener (Arm B)",
        "timestamp": datetime.now(UTC).isoformat(),
        "start_time": start_time,
        "commit_sha": commit_sha,
        "llm_mode": "fake" if smoke else "real",
        "models_used": models_used,
        "total_jobs_evaluated": len(all_evaluated_jobs),
        "jobs_per_persona": n_per_persona,
        "personas": target_personas,
        "simulator_harness": {
            "origin": "GigSim (student-built)",
            "client_decision_mode": "deterministic",
            "eval_flags": ["--simulator-only"],
        },
        "arm_a": {
            "strategy": "result_first_metric",
            "prompt_file": "agent/prompts/writer_arm_a.md",
            **overall_a,
        },
        "arm_b": {
            "strategy": "question_first_problem",
            "prompt_file": "agent/prompts/writer_arm_b.md",
            **overall_b,
        },
        "comparison": {
            "reply_rate_diff": round(overall_a["reply_rate"] - overall_b["reply_rate"], 4),
            "reply_z_stat": round(z_reply, 4),
            "reply_p_value": round(p_reply, 4),
            "reply_significant_05": bool(p_reply < 0.05),
            "reply_diff_ci_95": [round(ci_diff_reply[0], 4), round(ci_diff_reply[1], 4)],
            "hire_rate_diff": round(overall_a["hire_rate"] - overall_b["hire_rate"], 4),
            "hire_z_stat": round(z_hire, 4),
            "hire_p_value": round(p_hire, 4),
            "hire_significant_05": bool(p_hire < 0.05),
            "hire_diff_ci_95": [round(ci_diff_hire[0], 4), round(ci_diff_hire[1], 4)],
        },
        "by_persona": by_persona,
    }

    # 6. Save JSON results
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_file = output_dir / f"ab_experiment_{ts_str}.json"
    latest_file = output_dir / "ab_experiment_latest.json"

    run_file.write_text(json.dumps(experiment_report, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(experiment_report, indent=2), encoding="utf-8")
    print(f"[ab_experiment] Saved experiment results to {run_file} and {latest_file}")

    return experiment_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Extension X2 Proposal A/B Experiment")
    parser.add_argument("--n", type=int, default=40, help="Number of bid jobs per persona")
    parser.add_argument("--personas", nargs="+", default=DEFAULT_PERSONAS, help="Personas to evaluate")
    parser.add_argument("--simulator-only", action="store_true", help="Explicit confirmation for offline simulator harness")
    parser.add_argument("--smoke", action="store_true", help="Run in smoke test mode with hash embedder / fake llm")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching of generated proposals")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Datasets directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Results output directory")
    args = parser.parse_args()

    asyncio.run(
        run_ab_experiment(
            n_per_persona=args.n,
            personas=args.personas,
            simulator_only=args.simulator_only,
            smoke=args.smoke,
            use_cache=not args.no_cache,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
