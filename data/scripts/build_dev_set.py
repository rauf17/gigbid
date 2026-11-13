"""Dev evaluation set builder with gold labels (AI-4016 Assignment B4).

Constructs:
- evals/datasets/dev_<persona>.jsonl (200 jobs per persona, 150 in-category + 50 out-of-category)
- evals/datasets/tool_tasks.jsonl (40 tasks across marketplace, portfolio, and workspace MCP servers)

Gold labels:
- bid_or_skip: rule-based skip if scam, category mismatch, low skill overlap, or sub-floor budget
- is_scam and has_injection: from jobs_gold_labels.jsonl
- relevant_evidence_ids: persona case studies/repos/proposals matching job skills (Jaccard >= threshold, min 1, max 8)
- fair_price_band: [p25, p75] of comparable historical jobs
- n_requirements: count of explicit requirements extracted from job description

Deterministic, seed=42, zero LLM calls.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import yaml

DEFAULT_SEED = 42
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR.parent / "evals" / "datasets"

PERSONA_CATEGORIES = {
    "ai_ml": "AI/ML",
    "fullstack": "Full-Stack Web",
    "data_analyst": "Data Analysis",
}

TYPE_PRIORITY = {
    "case_study": 1,
    "repo_readme": 2,
    "repo_code": 3,
    "proposal": 4,
    "cv": 5,
    "review": 6,
}


def load_gold_rules(rules_path: Path) -> dict[str, Any]:
    """Loads gold labeling rules from YAML configuration."""
    if not rules_path.is_file():
        raise FileNotFoundError(f"Gold rules file not found: {rules_path}")
    return yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}


def load_all_jobs(processed_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Loads combined historical and stream jobs along with gold adversarial labels."""
    hist_file = processed_dir / "jobs_historical.jsonl"
    stream_file = processed_dir / "jobs_stream.jsonl"
    labels_file = processed_dir / "jobs_gold_labels.jsonl"

    labels_map: dict[str, dict[str, Any]] = {}
    if labels_file.is_file():
        for line in labels_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                labels_map[item["id"]] = item

    all_jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for path in (stream_file, hist_file):
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    job = json.loads(line)
                    if job["id"] not in seen_ids:
                        all_jobs.append(job)
                        seen_ids.add(job["id"])

    return all_jobs, labels_map


def load_persona_evidence_chunks(data_dir: Path, persona_id: str) -> list[dict[str, Any]]:
    """Loads indexed evidence chunks for a specific persona."""
    index_cache = data_dir / "processed" / "index" / f"{persona_id}_chunks.jsonl"
    if index_cache.is_file():
        chunks: list[dict[str, Any]] = []
        for line in index_cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(json.loads(line))
        return chunks

    # Fallback to building chunks dynamically if index cache not found
    from rag.ingest.chunkers import build_chunks_for_persona

    persona_dir = data_dir / "personas" / persona_id
    raw_chunks = build_chunks_for_persona(persona_id, persona_dir)
    return [c.model_dump() for c in raw_chunks]


def compute_skill_jaccard(skills_a: list[str], skills_b: list[str]) -> float:
    """Computes case-insensitive Jaccard index between two skill lists."""
    set_a = {s.lower().strip() for s in skills_a if s.strip()}
    set_b = {s.lower().strip() for s in skills_b if s.strip()}
    if not set_a or not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def compute_fair_price_band(
    job: dict[str, Any],
    historical_jobs: list[dict[str, Any]],
) -> list[float]:
    """Calculates [p25, p75] price distribution of comparable historical jobs."""
    job_cat = job.get("category", "")
    job_btype = job.get("budget_type", "fixed")
    job_skills = {s.lower().strip() for s in job.get("skills", [])}

    # 1. Matching category, budget_type, and skill overlap
    comparable_prices: list[float] = []
    category_prices: list[float] = []

    for h in historical_jobs:
        if h.get("category") != job_cat or h.get("budget_type") != job_btype:
            continue

        min_b = float(h.get("budget_min", 0.0))
        max_b = float(h.get("budget_max", 0.0))
        midpoint = (min_b + max_b) / 2.0 if (min_b and max_b) else (max_b or min_b)
        if midpoint <= 0:
            continue

        category_prices.append(midpoint)
        h_skills = {s.lower().strip() for s in h.get("skills", [])}
        if job_skills and (job_skills & h_skills):
            comparable_prices.append(midpoint)

    target_sample = comparable_prices if len(comparable_prices) >= 3 else category_prices
    if not target_sample:
        # Fallback to job's own bounds if no historical baseline available
        jmin = float(job.get("budget_min", 0.0))
        jmax = float(job.get("budget_max", 0.0))
        return [round(jmin, 2), round(jmax, 2)]

    p25 = float(round(np.percentile(target_sample, 25), 2))
    p75 = float(round(np.percentile(target_sample, 75), 2))
    return [p25, p75]


def select_relevant_evidence_ids(
    job_skills: list[str],
    evidence_chunks: list[dict[str, Any]],
    jaccard_threshold: float = 0.20,
    min_items: int = 1,
    max_items: int = 8,
) -> list[str]:
    """Selects ground-truth evidence chunk IDs based on skill overlap and type priority."""
    target_types = {"case_study", "repo_readme", "repo_code", "proposal"}
    candidates: list[tuple[float, int, str, str]] = []

    for chunk in evidence_chunks:
        ctype = chunk.get("type", "")
        if ctype not in target_types:
            continue

        c_skills = chunk.get("skills", [])
        jaccard = compute_skill_jaccard(job_skills, c_skills)
        priority = TYPE_PRIORITY.get(ctype, 10)
        cid = chunk.get("id", "")
        candidates.append((jaccard, priority, cid, ctype))

    # Sort descending by Jaccard, ascending by priority rank, ascending by chunk ID
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))

    # Filter by threshold
    qualified = [c[2] for c in candidates if c[0] >= jaccard_threshold]

    if not qualified:
        # Fallback to ensure min_items: pick top items by highest jaccard / overlap
        qualified = [c[2] for c in candidates[:min_items]]

    return qualified[:max_items]


def compute_bid_or_skip(
    job: dict[str, Any],
    persona_profile: dict[str, Any],
    is_scam: bool,
    rules: dict[str, Any],
) -> str:
    """Evaluates rule-based bid_or_skip gold label."""
    if is_scam:
        return "skip"

    persona_id = persona_profile.get("id", "")
    persona_rules = rules.get("personas", {}).get(persona_id, {})
    primary_category = persona_rules.get("primary_category") or PERSONA_CATEGORIES.get(persona_id, "")

    if job.get("category") != primary_category:
        return "skip"

    # Skill overlap ratio
    job_skills = {s.lower().strip() for s in job.get("skills", []) if s.strip()}
    persona_skills = {s.lower().strip() for s in persona_profile.get("skills", []) if s.strip()}

    if job_skills:
        overlap = len(job_skills & persona_skills)
        overlap_ratio = overlap / len(job_skills)
    else:
        overlap_ratio = 0.0

    min_overlap = persona_rules.get("min_skill_overlap_ratio", rules.get("min_skill_overlap_ratio", 0.35))
    if overlap_ratio < min_overlap:
        return "skip"

    # Floor rate evaluation
    btype = job.get("budget_type", "fixed")
    bmax = float(job.get("budget_max", 0.0))

    if btype == "hourly":
        floor_hourly = float(persona_profile.get("floor_hourly_rate", persona_rules.get("floor_hourly_rate", 60.0)))
        if bmax < floor_hourly:
            return "skip"
    elif btype == "fixed":
        min_fixed = float(persona_profile.get("min_fixed_rate", persona_rules.get("min_fixed_rate", 1000.0)))
        if bmax < min_fixed:
            return "skip"

    return "bid"


def build_dev_set_for_persona(
    persona_id: str,
    all_jobs: list[dict[str, Any]],
    historical_jobs: list[dict[str, Any]],
    labels_map: dict[str, dict[str, Any]],
    evidence_chunks: list[dict[str, Any]],
    persona_profile: dict[str, Any],
    rules: dict[str, Any],
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """Generates a deterministic 200-job dev set for a single freelancer persona."""
    primary_category = PERSONA_CATEGORIES.get(persona_id, "")

    in_cat_jobs = [j for j in all_jobs if j.get("category") == primary_category]
    out_cat_jobs = [j for j in all_jobs if j.get("category") != primary_category]

    # Deterministic sorting before sampling
    in_cat_jobs.sort(key=lambda x: x["id"])
    out_cat_jobs.sort(key=lambda x: x["id"])

    # Persona-specific deterministic seed
    rng = random.Random(seed + sum(ord(c) for c in persona_id))

    target_in = rules.get("target_in_category", 150)
    target_out = rules.get("target_out_category", 50)

    sampled_in = rng.sample(in_cat_jobs, min(target_in, len(in_cat_jobs)))
    sampled_out = rng.sample(out_cat_jobs, min(target_out, len(out_cat_jobs)))

    selected_jobs = sampled_in + sampled_out
    selected_jobs.sort(key=lambda x: x["id"])

    jaccard_thresh = rules.get("evidence_jaccard_threshold", 0.20)
    min_ev = rules.get("min_evidence_items", 1)
    max_ev = rules.get("max_evidence_items", 8)

    dev_rows: list[dict[str, Any]] = []

    for job in selected_jobs:
        jid = job["id"]
        adv_info = labels_map.get(jid, {})
        is_scam = bool(adv_info.get("is_scam", False))
        has_injection = bool(adv_info.get("has_injection", False))

        bid_or_skip = compute_bid_or_skip(job, persona_profile, is_scam, rules)
        evidence_ids = select_relevant_evidence_ids(
            job_skills=job.get("skills", []),
            evidence_chunks=evidence_chunks,
            jaccard_threshold=jaccard_thresh,
            min_items=min_ev,
            max_items=max_ev,
        )
        fair_price_band = compute_fair_price_band(job, historical_jobs)
        n_requirements = len(set(job.get("skills", [])))

        dev_rows.append(
            {
                "job": job,
                "gold": {
                    "bid_or_skip": bid_or_skip,
                    "is_scam": is_scam,
                    "has_injection": has_injection,
                    "relevant_evidence_ids": evidence_ids,
                    "fair_price_band": fair_price_band,
                    "n_requirements": n_requirements,
                },
            }
        )

    return dev_rows


def build_tool_tasks() -> list[dict[str, Any]]:
    """Builds 40 evaluation tasks across marketplace, portfolio, and workspace MCP servers.

    Schema per row: task_id, prompt, persona, server, expected_tool, expected_args_subset.
    """
    tasks = [
        # Marketplace MCP tasks (1-16)
        {
            "task_id": "task_01",
            "prompt": "Search active job listings in the AI/ML category matching vector search requirements.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "search_jobs",
            "expected_args_subset": {"category": "AI/ML", "query": "vector search"},
        },
        {
            "task_id": "task_02",
            "prompt": "Find newly posted Full-Stack Web jobs.",
            "persona": "fullstack",
            "server": "marketplace",
            "expected_tool": "search_jobs",
            "expected_args_subset": {"category": "Full-Stack Web"},
        },
        {
            "task_id": "task_03",
            "prompt": "Inspect full scope and budget for job posting job_stream_00041.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "get_job",
            "expected_args_subset": {"job_id": "job_stream_00041"},
        },
        {
            "task_id": "task_04",
            "prompt": "Retrieve project details for job ID job_hist_00001.",
            "persona": "data_analyst",
            "server": "marketplace",
            "expected_tool": "get_job",
            "expected_args_subset": {"job_id": "job_hist_00001"},
        },
        {
            "task_id": "task_05",
            "prompt": "Check hiring history and payment verification for client_270.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "get_client_history",
            "expected_args_subset": {"client_id": "client_270"},
        },
        {
            "task_id": "task_06",
            "prompt": "Evaluate client reputation and total marketplace spend for client_077.",
            "persona": "fullstack",
            "server": "marketplace",
            "expected_tool": "get_client_history",
            "expected_args_subset": {"client_id": "client_077"},
        },
        {
            "task_id": "task_07",
            "prompt": "Check the freelancer's current available Connects balance before bidding.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "get_connects_balance",
            "expected_args_subset": {},
        },
        {
            "task_id": "task_08",
            "prompt": "Read conversation message thread history for conversation conv_client_01.",
            "persona": "fullstack",
            "server": "marketplace",
            "expected_tool": "list_messages",
            "expected_args_subset": {"conversation_id": "conv_client_01"},
        },
        {
            "task_id": "task_09",
            "prompt": "Create a dry-run draft proposal for job job_stream_00041 with bid amount $2500.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "create_proposal_draft",
            "expected_args_subset": {
                "job_id": "job_stream_00041",
                "bid_amount": 2500.0,
                "dry_run": True,
            },
        },
        {
            "task_id": "task_10",
            "prompt": "Draft a proposal for job job_stream_00068 with bid of $450.",
            "persona": "fullstack",
            "server": "marketplace",
            "expected_tool": "create_proposal_draft",
            "expected_args_subset": {
                "job_id": "job_stream_00068",
                "bid_amount": 450.0,
            },
        },
        {
            "task_id": "task_11",
            "prompt": "Preview Connects cost and validation for submitting proposal prop_01 using dry_run.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "submit_proposal",
            "expected_args_subset": {
                "proposal_id": "prop_01",
                "dry_run": True,
            },
        },
        {
            "task_id": "task_12",
            "prompt": "Officially submit proposal prop_01 with idempotency key idemp-sub-100.",
            "persona": "fullstack",
            "server": "marketplace",
            "expected_tool": "submit_proposal",
            "expected_args_subset": {
                "proposal_id": "prop_01",
            },
        },
        {
            "task_id": "task_13",
            "prompt": "Send clarification reply in conversation conv_01 answering timeline question.",
            "persona": "ai_ml",
            "server": "marketplace",
            "expected_tool": "send_message",
            "expected_args_subset": {
                "conversation_id": "conv_01",
            },
        },
        {
            "task_id": "task_14",
            "prompt": "Search Data Analysis jobs requiring SQL and Tableau dashboards.",
            "persona": "data_analyst",
            "server": "marketplace",
            "expected_tool": "search_jobs",
            "expected_args_subset": {"category": "Data Analysis"},
        },
        {
            "task_id": "task_15",
            "prompt": "Inspect payment verification status for client_150.",
            "persona": "data_analyst",
            "server": "marketplace",
            "expected_tool": "get_client_history",
            "expected_args_subset": {"client_id": "client_150"},
        },
        {
            "task_id": "task_16",
            "prompt": "Check available Connects balance for data analyst persona.",
            "persona": "data_analyst",
            "server": "marketplace",
            "expected_tool": "get_connects_balance",
            "expected_args_subset": {},
        },
        # Portfolio MCP tasks (17-30)
        {
            "task_id": "task_17",
            "prompt": "Search portfolio evidence for past projects demonstrating sub-second RAG retrieval.",
            "persona": "ai_ml",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {"requirement": "sub-second RAG retrieval"},
        },
        {
            "task_id": "task_18",
            "prompt": "Find case studies demonstrating Stripe Connect and SaaS subscription billing.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {
                "requirement": "Stripe Connect subscription billing",
            },
        },
        {
            "task_id": "task_19",
            "prompt": "Retrieve full case study report and measured metrics for cs_01.",
            "persona": "ai_ml",
            "server": "portfolio",
            "expected_tool": "get_case_study",
            "expected_args_subset": {"id": "cs_01"},
        },
        {
            "task_id": "task_20",
            "prompt": "Load project narrative and architecture for case study cs_02.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "get_case_study",
            "expected_args_subset": {"id": "cs_02"},
        },
        {
            "task_id": "task_21",
            "prompt": "List all claimed technical skills for the AI/ML freelancer persona.",
            "persona": "ai_ml",
            "server": "portfolio",
            "expected_tool": "list_skills",
            "expected_args_subset": {},
        },
        {
            "task_id": "task_22",
            "prompt": "Search past winning proposals demonstrating Next.js frontend delivery.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {
                "requirement": "Next.js frontend development",
            },
        },
        {
            "task_id": "task_23",
            "prompt": "Find code evidence chunks demonstrating PyTorch neural network training.",
            "persona": "ai_ml",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {
                "requirement": "PyTorch neural network training",
            },
        },
        {
            "task_id": "task_24",
            "prompt": "Inspect case study details for cs_03 in the Data Analysis portfolio.",
            "persona": "data_analyst",
            "server": "portfolio",
            "expected_tool": "get_case_study",
            "expected_args_subset": {"id": "cs_03"},
        },
        {
            "task_id": "task_25",
            "prompt": "Retrieve proof of dbt data warehouse transformations for financial reporting.",
            "persona": "data_analyst",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {"requirement": "dbt data warehouse transformations"},
        },
        {
            "task_id": "task_26",
            "prompt": "Search client reviews praising communication and delivery speed.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {
                "requirement": "communication speed on-time delivery",
            },
        },
        {
            "task_id": "task_27",
            "prompt": "Load full markdown narrative for case study cs_04.",
            "persona": "ai_ml",
            "server": "portfolio",
            "expected_tool": "get_case_study",
            "expected_args_subset": {"id": "cs_04"},
        },
        {
            "task_id": "task_28",
            "prompt": "Search evidence matching Docker containerization and CI/CD pipelines.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "search_evidence",
            "expected_args_subset": {"requirement": "Docker containerization CI CD"},
        },
        {
            "task_id": "task_29",
            "prompt": "List all claimed technical skills for the fullstack freelancer persona.",
            "persona": "fullstack",
            "server": "portfolio",
            "expected_tool": "list_skills",
            "expected_args_subset": {},
        },
        {
            "task_id": "task_30",
            "prompt": "List all claimed technical skills for the data analyst persona.",
            "persona": "data_analyst",
            "server": "portfolio",
            "expected_tool": "list_skills",
            "expected_args_subset": {},
        },
        # Workspace MCP tasks (31-40)
        {
            "task_id": "task_31",
            "prompt": "Check freelancer calendar availability for client interviews next week.",
            "persona": "ai_ml",
            "server": "workspace",
            "expected_tool": "get_available_slots",
            "expected_args_subset": {"start_date": "2026-11-16", "end_date": "2026-11-20"},
        },
        {
            "task_id": "task_32",
            "prompt": "Place a tentative calendar hold for an interview slot with client FinTech Corp.",
            "persona": "ai_ml",
            "server": "workspace",
            "expected_tool": "place_tentative_hold",
            "expected_args_subset": {
                "slot_id": "slot_20261117_1400",
                "client_name": "FinTech Corp",
            },
        },
        {
            "task_id": "task_33",
            "prompt": "Draft an introductory email acknowledging an interview request for job job_stream_00041.",
            "persona": "ai_ml",
            "server": "workspace",
            "expected_tool": "create_email_draft",
            "expected_args_subset": {
                "recipient": "client@fintechcorp.example.com",
                "subject": "Interview Availability - Elena Rostova",
            },
        },
        {
            "task_id": "task_34",
            "prompt": "Find 30-minute available morning slots between November 18 and November 19.",
            "persona": "fullstack",
            "server": "workspace",
            "expected_tool": "get_available_slots",
            "expected_args_subset": {"start_date": "2026-11-18", "end_date": "2026-11-19"},
        },
        {
            "task_id": "task_35",
            "prompt": "Hold a 60-minute technical evaluation slot for SaaS Growth Partners.",
            "persona": "fullstack",
            "server": "workspace",
            "expected_tool": "place_tentative_hold",
            "expected_args_subset": {
                "slot_id": "slot_20261118_1000",
                "client_name": "SaaS Growth Partners",
            },
        },
        {
            "task_id": "task_36",
            "prompt": "Draft a project kickoff milestone agreement email to client Marcus Vance Client.",
            "persona": "fullstack",
            "server": "workspace",
            "expected_tool": "create_email_draft",
            "expected_args_subset": {
                "recipient": "client@saasbilling.example.com",
                "subject": "Milestone Schedule - Full-Stack SaaS Portal",
            },
        },
        {
            "task_id": "task_37",
            "prompt": "Check afternoon availability for client consultations on Friday.",
            "persona": "data_analyst",
            "server": "workspace",
            "expected_tool": "get_available_slots",
            "expected_args_subset": {"start_date": "2026-11-20", "end_date": "2026-11-20"},
        },
        {
            "task_id": "task_38",
            "prompt": "Draft follow-up email confirming delivery of initial RAG evaluation benchmarks.",
            "persona": "ai_ml",
            "server": "workspace",
            "expected_tool": "create_email_draft",
            "expected_args_subset": {
                "recipient": "cto@legaltech.example.com",
                "subject": "RAG Evaluation Benchmark Report Delivered",
            },
        },
        {
            "task_id": "task_39",
            "prompt": "Place a tentative hold for data pipeline kickoff meeting with DataOps Ltd.",
            "persona": "data_analyst",
            "server": "workspace",
            "expected_tool": "place_tentative_hold",
            "expected_args_subset": {
                "slot_id": "slot_20261119_1500",
                "client_name": "DataOps Ltd",
            },
        },
        {
            "task_id": "task_40",
            "prompt": "Check freelancer open calendar slots for client introductory calls.",
            "persona": "data_analyst",
            "server": "workspace",
            "expected_tool": "get_available_slots",
            "expected_args_subset": {"start_date": "2026-11-16", "end_date": "2026-11-17"},
        },
    ]
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build synthetic dev evaluation sets with gold labels.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"RNG seed (default: {DEFAULT_SEED})")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Target output directory for dev sets",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rules_path = output_dir / "gold_rules.yaml"
    rules = load_gold_rules(rules_path)

    data_dir = DEFAULT_DATA_DIR
    processed_dir = data_dir / "processed"

    all_jobs, labels_map = load_all_jobs(processed_dir)
    historical_jobs = [j for j in all_jobs if j.get("id", "").startswith("job_hist_")]

    print(f"[build_dev_set] Loaded {len(all_jobs)} total jobs ({len(historical_jobs)} historical).")

    # Generate dev sets for each persona
    for persona_id in ("ai_ml", "fullstack", "data_analyst"):
        persona_file = data_dir / "personas" / persona_id / "profile.json"
        if not persona_file.is_file():
            print(f"[build_dev_set] WARNING: Persona profile not found for {persona_id}, skipping.")
            continue

        persona_profile = json.loads(persona_file.read_text(encoding="utf-8"))
        evidence_chunks = load_persona_evidence_chunks(data_dir, persona_id)

        rows = build_dev_set_for_persona(
            persona_id=persona_id,
            all_jobs=all_jobs,
            historical_jobs=historical_jobs,
            labels_map=labels_map,
            evidence_chunks=evidence_chunks,
            persona_profile=persona_profile,
            rules=rules,
            seed=args.seed,
        )

        out_file = output_dir / f"dev_{persona_id}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)

        bids = sum(1 for r in rows if r["gold"]["bid_or_skip"] == "bid")
        skips = sum(1 for r in rows if r["gold"]["bid_or_skip"] == "skip")
        scams = sum(1 for r in rows if r["gold"]["is_scam"])
        injections = sum(1 for r in rows if r["gold"]["has_injection"])

        print(
            f"[build_dev_set] {persona_id}: {len(rows)} dev jobs -> {out_file.name} "
            f"(bids={bids}, skips={skips}, scams={scams}, injections={injections})"
        )

    # Generate tool_tasks.jsonl
    tool_tasks = build_tool_tasks()
    tasks_file = output_dir / "tool_tasks.jsonl"
    with open(tasks_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(t) + "\n" for t in tool_tasks)

    print(f"[build_dev_set] Generated {len(tool_tasks)} tool tasks -> {tasks_file.name}")


if __name__ == "__main__":
    main()
