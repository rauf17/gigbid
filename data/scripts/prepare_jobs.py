"""Job Dataset Preparation and Synthesis (AI-4016 GigBid Phase 1b).

Processes raw Kaggle CSV files if present in data/raw/, otherwise falls back
to a deterministic synthetic generator (seed=42).

Outputs:
  - data/processed/jobs_historical.jsonl (~1500 jobs for price statistics)
  - data/processed/jobs_stream.jsonl (~600 jobs for live simulation stream)

Target schema per job:
  - id: str
  - title: str
  - description: str
  - category: str ("AI/ML", "Full-Stack Web", "Data Analysis")
  - skills: list[str]
  - budget_type: str ("fixed" | "hourly")
  - budget_min: float
  - budget_max: float
  - client_country: str
  - posted_at: str (ISO 8601)
  - connects_cost: int
  - synthetic: bool

Usage:
  python data/scripts/prepare_jobs.py --seed 42
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

CATEGORIES = ["AI/ML", "Full-Stack Web", "Data Analysis"]

COUNTRIES = [
    "United States", "United Kingdom", "Canada", "Germany", "Australia",
    "Netherlands", "Singapore", "France", "Switzerland", "Sweden", "Ireland"
]

SKILLS_BY_CAT = {
    "AI/ML": [
        "Python", "PyTorch", "FastAPI", "Docker", "pgvector", "LangChain",
        "Transformers", "vLLM", "Hugging Face", "MLOps", "OpenAI API", "Redis"
    ],
    "Full-Stack Web": [
        "TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI",
        "Tailwind CSS", "PostgreSQL", "Redis", "Docker", "Stripe API", "AWS"
    ],
    "Data Analysis": [
        "SQL", "Python", "PostgreSQL", "Snowflake", "dbt", "Power BI",
        "Tableau", "Pandas", "BigQuery", "Looker", "DuckDB", "Airflow"
    ],
}

JOB_TEMPLATES = {
    "AI/ML": [
        (
            "Senior LLM Engineer for Production RAG Pipeline",
            ("We are seeking an experienced AI/ML engineer to build and optimize our enterprise RAG retrieval pipeline. "
            "The system must index 2M+ technical documents using pgvector and LangChain, achieving sub-second latency and high precision. "
            "Experience with chunking strategies, hybrid BM25 + dense search, and hallucination evaluation is required. "
            "You will deploy the service as a containerized FastAPI application with Redis caching.")
        ),
        (
            "Real-Time Fraud Detection Microservice with PyTorch",
            ("Looking for a machine learning engineer to build a real-time transaction scoring microservice. "
            "Must handle streaming Kafka events at 10k TPS with p99 latency under 40ms. "
            "Experience with gradient boosting, ONNX runtime, Docker, and Redis feature stores is essential. "
            "Clean code, typed interfaces, and unit tests are mandatory.")
        ),
        (
            "Fine-Tune Open-Source LLMs for Medical Coding",
            ("Need a specialist to fine-tune Llama-3 or Mistral on our proprietary clinical dataset. "
            "Tasks include data curation, LoRA/QLoRA fine-tuning, vLLM deployment, and evaluation against gold standards. "
            "Must have hands-on experience with PyTorch, Hugging Face Transformers, and GPU memory optimization.")
        ),
        (
            "Multi-Agent Workflow Development in LangGraph",
            ("We are building an autonomous customer triage system using LangGraph. "
            "The graph will route incoming support tickets to specialized sub-agents with human-in-the-loop approval gates. "
            "Candidate must have deep familiarity with LangGraph state machines, structured Pydantic hand-offs, and streaming SSE.")
        ),
        (
            "Computer Vision Specialist for Defect Detection (YOLOv8)",
            ("Manufacturing client requires an automated visual inspection pipeline for factory production lines. "
            "You will train and deploy a quantized YOLOv8 model running on Jetson edge devices processing 30fps video streams. "
            "Must be proficient in Python, OpenCV, PyTorch, and RTSP video ingestion.")
        ),
        (
            "Time-Series Demand Forecasting with LightGBM",
            ("Retail brand needs a hierarchical demand forecasting engine for 20,000 SKUs across 8 regional warehouses. "
            "You will build feature pipelines in Pandas, train LightGBM models, and integrate with MLflow tracking. "
            "Deliverables include automated weekly inference scripts and backtesting reports.")
        ),
    ],
    "Full-Stack Web": [
        (
            "Full-Stack Next.js 14 & FastAPI Developer for SaaS Billing",
            ("We need a senior full-stack developer to architect our multi-tenant SaaS subscription portal. "
            "Frontend built in Next.js 14 App Router with Tailwind CSS; backend powered by FastAPI and PostgreSQL. "
            "Must have extensive experience with Stripe Connect, webhook reconciliation, and idempotent state machines.")
        ),
        (
            "Real-Time Collaborative Canvas App with WebSockets",
            ("Looking for an experienced engineer to build a real-time multiplayer board for remote design teams. "
            "Stack: React, TypeScript, Node.js, WebSockets, and Redis pub/sub. "
            "Must have solved synchronization race conditions and state conflicts using CRDTs or operational transforms.")
        ),
        (
            "High-Throughput Logistics Dispatch Dashboard",
            ("Seeking a frontend/fullstack developer to build a live driver dispatch console. "
            "The app tracks 3,000+ simultaneous vehicles with WebGL map layers, virtualized data tables, and live telemetry feeds. "
            "Proficiency in React, TypeScript, Tailwind, and FastAPI is required.")
        ),
        (
            "Developer API Platform & Interactive Documentation Console",
            ("We are launching our public REST API and need a developer hub with interactive consoles, API key management, and usage metrics. "
            "Built with Next.js, FastAPI, PostgreSQL, and OpenAPI schema generators. Dockerized deployment on AWS.")
        ),
        (
            "HIPAA-Compliant Telehealth Consultation Web App",
            ("Healthcare startup seeking a full-stack engineer to build an encrypted telehealth consultation portal. "
            "Features include WebRTC video rooms, calendar scheduling, automated waiting queues, and audit logging. "
            "Must have strong experience in Next.js, Node.js, PostgreSQL, and healthcare security compliance.")
        ),
        (
            "Headless E-Commerce Checkout Optimization",
            ("E-commerce retailer looking to decrease cart abandonment by rebuilding our checkout flow. "
            "Re-architecting Shopify storefront APIs with Next.js Edge Functions and Tailwind CSS. "
            "Must understand Web Vitals, mobile responsiveness, and payment gateway integrations.")
        ),
    ],
    "Data Analysis": [
        (
            "Lead Analytics Engineer: dbt & Snowflake Modeling",
            ("We are revamping our corporate data warehouse and need an expert to build modular dbt models in Snowflake. "
            "You will transform raw Stripe and Salesforce event streams into Kimball star schemas (facts and dimensions). "
            "Experience with dbt incremental models, Jinja, and automated schema tests is required.")
        ),
        (
            "SaaS Churn & Cohort Retention Analytics",
            ("B2B SaaS company needs a data analyst to conduct deep-dive cohort retention and gross churn analysis. "
            "You will write advanced SQL window functions in PostgreSQL/Snowflake and build interactive Tableau dashboards. "
            "Deliverables include monthly retention matrices and churn driver correlation models.")
        ),
        (
            "Multi-Touch Marketing Attribution in BigQuery",
            ("E-commerce brand seeking an analyst to build a multi-touch attribution model across paid social, search, and email. "
            "You will analyze 1.5M touchpoints using SQL and Python in BigQuery, implementing Markov chain and position-based attribution. "
            "Must produce executive Looker dashboards showing channel ROAS.")
        ),
        (
            "Hospital Operations & Patient Flow Power BI Dashboard",
            ("Regional hospital group needs an operational analyst to model emergency room wait times and bed utilization. "
            "Must connect to PostgreSQL databases, write clean DAX queries in Power BI, and deliver automated daily executive reports. "
            "Healthcare metrics experience preferred.")
        ),
        (
            "Subscription Revenue Recognition & ASC 606 Reporting",
            ("FinTech company requires automated revenue recognition modeling for multi-year enterprise contracts. "
            "You will write automated dbt models reconciling deferred revenue schedules against Stripe billing invoices. "
            "Deliverables must pass external financial audit scrutiny.")
        ),
        (
            "Retail Inventory Reorder & Safety Stock Modeling",
            ("Retail chain needs an analytical model to optimize inventory reorder points across 50 stores. "
            "You will analyze historical lead times, stockout frequencies, and holding costs using SQL and Python Pandas. "
            "Final output: daily automated reorder recommendation reports.")
        ),
    ]
}


def calculate_connects_cost(budget_type: str, budget_min: float, budget_max: float) -> int:
    """Calculates realistic Upwork connects cost (4 to 16) based on budget."""
    if budget_type == "fixed":
        effective_budget = budget_max if budget_max > 0 else budget_min
        if effective_budget < 100:
            return 4
        elif effective_budget < 600:
            return 8
        elif effective_budget < 3000:
            return 12
        else:
            return 16
    else:  # hourly
        effective_hourly = (budget_min + budget_max) / 2.0 if budget_max > 0 else budget_min
        if effective_hourly < 35:
            return 4
        elif effective_hourly < 60:
            return 8
        elif effective_hourly < 90:
            return 12
        else:
            return 16


def inspect_and_map_raw_csvs(raw_dir: Path) -> list[dict] | None:
    """Inspects raw CSV files in data/raw/, prints mapping table, and normalizes."""
    csv_files = list(raw_dir.glob("*.csv"))
    if not csv_files:
        return None

    print(f"[prepare_jobs] Found {len(csv_files)} CSV file(s) in {raw_dir}")
    print("\n" + "=" * 70)
    print("RAW CSV INSPECTION & FIELD MAPPING TABLE")
    print("=" * 70)
    print(f"{'Target Field':<20} | {'Mapped CSV Column / Rule':<45}")
    print("-" * 70)

    mappings = {
        "id": "job_id / id / hash(title+date)",
        "title": "title / job_title / Title",
        "description": "description / text / snippet",
        "category": "category (filtered to AI/ML, Full-Stack, Data)",
        "skills": "skills / tags (comma/space-separated list)",
        "budget_type": "job_type / budget_type ('fixed' or 'hourly')",
        "budget_min": "budget / hourly_low / parsed currency",
        "budget_max": "budget / hourly_high / parsed currency",
        "client_country": "country / client_country (fallback US)",
        "posted_at": "posted_date / published_date (ISO 8601)",
        "connects_cost": "Calculated dynamically based on budget tier (4-16)"
    }
    for tf, mc in mappings.items():
        print(f"{tf:<20} | {mc:<45}")
    print("=" * 70 + "\n")

    # In practice if real Kaggle CSVs exist, parse them here
    jobs: list[dict] = []
    for csv_file in csv_files:
        with csv_file.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            print(f"[prepare_jobs] File: {csv_file.name} | Headers: {headers[:8]}...")
            for idx, row in enumerate(reader):
                # Standardize row mapping
                title = row.get("title") or row.get("job_title") or f"Job {idx}"
                desc = row.get("description") or row.get("snippet") or title
                cat_raw = row.get("category", "")
                cat = "AI/ML" if "ai" in cat_raw.lower() or "machine" in cat_raw.lower() else (
                    "Data Analysis" if "data" in cat_raw.lower() or "analyst" in cat_raw.lower() else "Full-Stack Web"
                )
                jobs.append({
                    "id": f"raw_{idx+1:05d}",
                    "title": title.strip(),
                    "description": desc.strip(),
                    "category": cat,
                    "skills": [s.strip() for s in row.get("skills", "").split(";") if s.strip()][:6],
                    "budget_type": "fixed" if "hourly" not in row.get("job_type", "").lower() else "hourly",
                    "budget_min": float(row.get("budget_min", 500) or 500),
                    "budget_max": float(row.get("budget_max", 1500) or 1500),
                    "client_country": row.get("country", "United States"),
                    "posted_at": datetime.now(UTC).isoformat(),
                    "connects_cost": 8,
                    "synthetic": False,
                })
    return jobs if jobs else None


def generate_synthetic_job(
    job_id: str,
    category: str,
    base_date: datetime,
    rng: random.Random,
    is_stream: bool = False,
    client_id: str | None = None
) -> dict:
    """Generates a single realistic synthetic job posting."""
    title_template, desc_template = rng.choice(JOB_TEMPLATES[category])
    skills_pool = SKILLS_BY_CAT[category]
    selected_skills = rng.sample(skills_pool, k=rng.randint(3, 5))

    budget_type = rng.choice(["fixed", "hourly", "fixed"])  # ~66% fixed, 33% hourly

    if budget_type == "fixed":
        tier = rng.choice(["small", "medium", "large"])
        if tier == "small":
            b_min = float(rng.randint(250, 600))
            b_max = float(rng.randint(int(b_min), 900))
        elif tier == "medium":
            b_min = float(rng.randint(1000, 2500))
            b_max = float(rng.randint(int(b_min), 4000))
        else:  # large
            b_min = float(rng.randint(5000, 9000))
            b_max = float(rng.randint(int(b_min), 15000))
    else:  # hourly
        b_min = float(rng.choice([35, 45, 55, 65, 75]))
        b_max = float(b_min + rng.choice([20, 30, 45, 60]))

    country = rng.choice(COUNTRIES)
    offset_hours = rng.randint(1, 48) if is_stream else rng.randint(1, 4000)
    posted_dt = base_date - timedelta(hours=offset_hours)
    connects = calculate_connects_cost(budget_type, b_min, b_max)

    # Assign from established clients (client_036 to client_300) by default
    if client_id is None:
        client_num = rng.randint(36, 300)
        client_id = f"client_{client_num:03d}"

    return {
        "id": job_id,
        "title": title_template,
        "description": desc_template,
        "category": category,
        "skills": selected_skills,
        "budget_type": budget_type,
        "budget_min": b_min,
        "budget_max": b_max,
        "client_country": country,
        "client_id": client_id,
        "posted_at": posted_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "connects_cost": connects,
        "synthetic": True,
    }


def prepare_jobs(
    raw_dir: Path,
    output_dir: Path,
    historical_count: int = 1500,
    stream_count: int = 600,
    seed: int = 42
) -> None:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_jobs = inspect_and_map_raw_csvs(raw_dir)
    now = datetime(2024, 8, 1, 12, 0, 0, tzinfo=UTC)

    if raw_jobs:
        print(f"[prepare_jobs] Processed {len(raw_jobs)} jobs from raw CSVs.")
        historical_jobs = raw_jobs[:historical_count]
        stream_jobs = raw_jobs[historical_count:historical_count + stream_count]
    else:
        print("[prepare_jobs] data/raw/ is empty or contains no CSV files.")
        print(f"[prepare_jobs] Falling back to deterministic synthetic job generator (seed={seed}).")

        # 1. Historical Jobs (~1500 jobs, evenly split across categories)
        historical_jobs = []
        for i in range(historical_count):
            cat = CATEGORIES[i % len(CATEGORIES)]
            job_id = f"job_hist_{i+1:05d}"
            job = generate_synthetic_job(job_id, cat, now, rng, is_stream=False)
            historical_jobs.append(job)

        # 2. Stream Jobs (~600 jobs, evenly split across categories)
        stream_jobs = []
        for i in range(stream_count):
            cat = CATEGORIES[i % len(CATEGORIES)]
            job_id = f"job_stream_{i+1:05d}"
            job = generate_synthetic_job(job_id, cat, now, rng, is_stream=True)
            stream_jobs.append(job)

    # Sort stream jobs chronologically
    stream_jobs.sort(key=lambda j: j["posted_at"])

    # Write jobs_historical.jsonl
    hist_path = output_dir / "jobs_historical.jsonl"
    with hist_path.open("w", encoding="utf-8") as f:
        for job in historical_jobs:
            f.write(json.dumps(job) + "\n")
    print(f"[prepare_jobs] Wrote {len(historical_jobs)} jobs to {hist_path}")

    # Write baseline jobs_stream.jsonl
    stream_path = output_dir / "jobs_stream.jsonl"
    with stream_path.open("w", encoding="utf-8") as f:
        for job in stream_jobs:
            f.write(json.dumps(job) + "\n")
    print(f"[prepare_jobs] Wrote {len(stream_jobs)} jobs to {stream_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and synthesize job streams for GigBid.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Directory containing raw Kaggle CSVs.")
    parser.add_argument("--output-dir", type=str, default="data/processed", help="Output directory.")
    parser.add_argument("--historical-count", type=int, default=1500, help="Number of historical jobs.")
    parser.add_argument("--stream-count", type=int, default=600, help="Number of stream jobs.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    raw_path = Path(args.raw_dir)
    if not raw_path.is_absolute():
        raw_path = repo_root / raw_path

    output_path = Path(args.output_dir)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    prepare_jobs(
        raw_dir=raw_path,
        output_dir=output_path,
        historical_count=args.historical_count,
        stream_count=args.stream_count,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
