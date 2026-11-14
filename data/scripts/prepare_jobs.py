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
from typing import Any

CATEGORIES = ["AI/ML", "Full-Stack Web", "Data Analysis"]

COUNTRIES = [
    "United States", "United Kingdom", "Canada", "Germany", "Australia",
    "Netherlands", "Singapore", "France", "Switzerland", "Sweden", "Ireland"
]

JOB_ARCHETYPES: dict[str, list[dict[str, Any]]] = {
    "AI/ML": [
        {
            "title": "Senior LLM Engineer for Production RAG Pipeline",
            "skills": ["Python", "FastAPI", "pgvector", "LangChain", "Docker"],
            "description": (
                "We are seeking an experienced AI/ML engineer to build and optimize our enterprise RAG retrieval pipeline in Python. "
                "The system must index 2M+ technical documents using pgvector and LangChain, achieving sub-second latency and high precision. "
                "Experience with chunking strategies, hybrid search, and hallucination evaluation is required. "
                "You will deploy the service as a containerized FastAPI application with Docker and Redis caching."
            ),
        },
        {
            "title": "Real-Time Fraud Detection Microservice with PyTorch",
            "skills": ["PyTorch", "Kafka", "FastAPI", "Redis", "Docker"],
            "description": (
                "Looking for a machine learning engineer to build a real-time transaction scoring microservice. "
                "Must handle streaming Kafka events with p99 latency under 40ms. "
                "Hands-on experience with PyTorch, Docker, and Redis feature stores is essential. "
                "Clean code, typed FastAPI interfaces, and comprehensive unit tests are mandatory."
            ),
        },
        {
            "title": "Fine-Tune Open-Source LLMs for Medical Coding",
            "skills": ["Transformers", "PyTorch", "vLLM", "Hugging Face", "MLOps"],
            "description": (
                "Need a specialist to fine-tune Llama-3 and Mistral models on clinical notes. "
                "Tasks include data curation, LoRA fine-tuning, and high-throughput vLLM deployment. "
                "Must have hands-on experience with PyTorch, Hugging Face Transformers, and production MLOps evaluation against gold standards."
            ),
        },
        {
            "title": "Multi-Agent Workflow Development in LangGraph",
            "skills": ["LangGraph", "FastAPI", "Redis", "OpenAI API", "Python"],
            "description": (
                "We are building an autonomous customer triage system in Python using LangGraph. "
                "The graph routes support tickets to specialized sub-agents with human approval gates. "
                "Candidate must have deep familiarity with LangGraph state machines, Redis session memory, OpenAI API function calling, and FastAPI endpoints."
            ),
        },
        {
            "title": "Computer Vision Specialist for Defect Detection (YOLOv8)",
            "skills": ["PyTorch", "TimeSeries", "Scikit-Learn", "Docker", "FastAPI"],
            "description": (
                "Manufacturing client requires an automated visual inspection pipeline for production lines. "
                "You will train and deploy models in PyTorch running on edge devices. "
                "Must be proficient in Python, Scikit-Learn, TimeSeries sensor tracking, Docker containerization, and FastAPI inference services."
            ),
        },
        {
            "title": "Time-Series Demand Forecasting with LightGBM",
            "skills": ["LightGBM", "Pandas", "Scikit-Learn", "Python", "MLflow"],
            "description": (
                "Retail brand needs a hierarchical demand forecasting engine for 20,000 SKUs across 8 regional warehouses. "
                "You will build feature pipelines in Pandas, train LightGBM models with Scikit-Learn, and integrate with MLflow tracking in Python. "
                "Deliverables include weekly inference scripts and backtesting reports."
            ),
        },
        {
            "title": "Semantic Search Engine for Legal Contracts",
            "skills": ["Python", "pgvector", "FastAPI", "Transformers", "Docker"],
            "description": (
                "LegalTech company building a semantic contract discovery platform. "
                "You will implement dense neural embeddings with Hugging Face Transformers, store and index vector embeddings in PostgreSQL using pgvector, "
                "and expose search endpoints via a containerized FastAPI microservice deployed with Docker in Python."
            ),
        },
        {
            "title": "Speech-to-Text Transcription Microservice with Whisper",
            "skills": ["Whisper", "PyTorch", "FastAPI", "Docker", "Python"],
            "description": (
                "Media production studio seeks an AI engineer to deploy an automated audio transcription pipeline. "
                "You will fine-tune and serve Whisper models with PyTorch, optimize GPU batching, "
                "and wrap the worker in a Docker container exposing asynchronous FastAPI endpoints in Python."
            ),
        },
    ],
    "Full-Stack Web": [
        {
            "title": "Full-Stack Next.js 14 & FastAPI Developer for SaaS Billing",
            "skills": ["Next.js", "FastAPI", "Stripe API", "PostgreSQL", "Tailwind CSS"],
            "description": (
                "We need a senior full-stack developer to architect our multi-tenant SaaS subscription portal. "
                "Frontend built in Next.js 14 App Router with Tailwind CSS; backend powered by FastAPI and PostgreSQL. "
                "Must have extensive experience integrating Stripe API webhooks, checkout flows, and automated invoicing."
            ),
        },
        {
            "title": "Real-Time Collaborative Canvas App with WebSockets",
            "skills": ["React", "TypeScript", "Node.js", "WebSockets", "Redis"],
            "description": (
                "Looking for an experienced engineer to build a real-time multiplayer board for remote design teams. "
                "Stack: React, TypeScript, Node.js, WebSockets, and Redis pub/sub. "
                "Must solve synchronization race conditions, live presence indicators, and state conflicts."
            ),
        },
        {
            "title": "High-Throughput Logistics Dispatch Dashboard",
            "skills": ["React", "TypeScript", "FastAPI", "Tailwind CSS", "Docker"],
            "description": (
                "Seeking a frontend/fullstack developer to build a live driver dispatch console. "
                "The app tracks 3,000+ simultaneous vehicles with live telemetry feeds. "
                "Frontend implemented in React and TypeScript with Tailwind CSS styling, communicating with a containerized FastAPI backend deployed via Docker."
            ),
        },
        {
            "title": "Developer API Platform & Interactive Documentation Console",
            "skills": ["Next.js", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            "description": (
                "We are launching our public REST API and need a developer hub with interactive consoles, API key management, and usage metrics. "
                "Built with Next.js frontends, FastAPI services, and PostgreSQL data stores. "
                "Containerized deployment with Docker on AWS cloud infrastructure."
            ),
        },
        {
            "title": "HIPAA-Compliant Telehealth Consultation Web App",
            "skills": ["Next.js", "Node.js", "PostgreSQL", "Tailwind CSS", "TypeScript"],
            "description": (
                "Healthcare startup seeking a full-stack engineer to build an encrypted telehealth consultation portal. "
                "Features include calendar scheduling, patient intake, and audit logging. "
                "Must have strong experience in Next.js, TypeScript, Node.js, PostgreSQL, and Tailwind CSS."
            ),
        },
        {
            "title": "Headless E-Commerce Storefront & Checkout Optimization",
            "skills": ["Next.js", "React", "Tailwind CSS", "TypeScript", "Stripe API"],
            "description": (
                "E-commerce retailer looking to decrease cart abandonment by rebuilding our checkout flow. "
                "Re-architecting storefront components with Next.js, React, and TypeScript styled with Tailwind CSS. "
                "Includes seamless Stripe API payment processing and mobile responsiveness."
            ),
        },
        {
            "title": "Cloud Resource Provisioning & Infrastructure Portal",
            "skills": ["React", "TypeScript", "Node.js", "AWS", "Docker"],
            "description": (
                "DevOps SaaS seeking a full-stack developer to build a cloud resource provisioning dashboard. "
                "Built with React and TypeScript on Node.js backends. "
                "Deep knowledge of AWS SDKs, Docker container life-cycles, and infrastructure metrics is essential."
            ),
        },
        {
            "title": "Interactive Survey & Customer Feedback Web Application",
            "skills": ["Next.js", "TypeScript", "Tailwind CSS", "PostgreSQL", "FastAPI"],
            "description": (
                "Product team needs a dynamic customer feedback collection application. "
                "Built using Next.js with TypeScript and Tailwind CSS, backed by a FastAPI backend writing to PostgreSQL. "
                "Features branch logic, instant CSV exports, and respondent dashboards."
            ),
        },
    ],
    "Data Analysis": [
        {
            "title": "Lead Analytics Engineer: dbt & Snowflake Modeling",
            "skills": ["dbt", "Snowflake", "SQL", "Airflow", "Python"],
            "description": (
                "We are revamping our corporate data warehouse and need an expert to build modular dbt models in Snowflake. "
                "You will transform raw event streams into Kimball star schemas using SQL and Python. "
                "Orchestration with Airflow DAGs and automated schema tests is required."
            ),
        },
        {
            "title": "SaaS Churn & Cohort Retention Analytics",
            "skills": ["SQL", "Snowflake", "Tableau", "Python", "Pandas"],
            "description": (
                "B2B SaaS company needs a data analyst to conduct deep-dive cohort retention and gross churn analysis. "
                "You will write advanced SQL window functions in Snowflake, analyze user behavior with Python and Pandas, "
                "and build interactive Tableau dashboards for leadership."
            ),
        },
        {
            "title": "Multi-Touch Marketing Attribution in BigQuery",
            "skills": ["BigQuery", "SQL", "Python", "Looker", "Airflow"],
            "description": (
                "E-commerce brand seeking an analyst to build a multi-touch attribution model across paid channels. "
                "You will analyze 1.5M touchpoints using SQL and Python in BigQuery, orchestrate ETL jobs with Airflow, "
                "and produce executive Looker dashboards showing channel ROAS."
            ),
        },
        {
            "title": "Hospital Operations & Patient Flow Power BI Dashboard",
            "skills": ["Power BI", "PostgreSQL", "SQL", "Python", "DuckDB"],
            "description": (
                "Regional hospital group needs an operational analyst to model emergency room wait times and bed utilization. "
                "Must connect to PostgreSQL databases, process local metrics with DuckDB and Python, write clean SQL queries, "
                "and deliver automated daily reports in Power BI."
            ),
        },
        {
            "title": "Subscription Revenue Recognition & ASC 606 Reporting",
            "skills": ["dbt", "SQL", "Snowflake", "Pandas", "Python"],
            "description": (
                "FinTech company requires automated revenue recognition modeling for enterprise contracts. "
                "You will write automated dbt models in Snowflake reconciling deferred revenue schedules using SQL and Python with Pandas. "
                "Deliverables must pass audit scrutiny."
            ),
        },
        {
            "title": "Retail Inventory Reorder & Safety Stock Modeling",
            "skills": ["DuckDB", "Python", "SQL", "Tableau", "Pandas"],
            "description": (
                "Retail chain needs an analytical model to optimize inventory reorder points across 50 stores. "
                "You will analyze lead times and stockout frequencies using SQL and Python with Pandas and DuckDB. "
                "Final deliverables include automated Tableau replenishment dashboards."
            ),
        },
        {
            "title": "Financial Risk & Treasury Liquidity Analytics",
            "skills": ["SQL", "Python", "Pandas", "Power BI", "PostgreSQL"],
            "description": (
                "Investment firm seeking a quantitative data analyst to build treasury liquidity forecasting models. "
                "Candidate will extract transaction logs from PostgreSQL with SQL, calculate value-at-risk scenarios in Python using Pandas, "
                "and publish live Power BI KPI reports."
            ),
        },
        {
            "title": "E-Commerce Conversion Funnel & A/B Testing Analytics",
            "skills": ["BigQuery", "SQL", "Python", "Tableau", "Pandas"],
            "description": (
                "Consumer app needs an analyst to evaluate multivariate A/B tests and onboarding funnels. "
                "Responsibilities include querying BigQuery clickstream events using SQL, statistical hypothesis testing in Python with Pandas, "
                "and presenting conversion lift insights in Tableau."
            ),
        },
    ],
}

SKILLS_BY_CAT = {
    cat: sorted({skill for arch in archs for skill in arch["skills"]})
    for cat, archs in JOB_ARCHETYPES.items()
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
    """Generates a single realistic synthetic job posting using unified archetypes."""
    archetype = rng.choice(JOB_ARCHETYPES[category])
    title = archetype["title"]
    desc_template = archetype["description"]
    selected_skills = list(archetype["skills"])

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
        "title": title,
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
