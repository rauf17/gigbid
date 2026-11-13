"""Client Data Model and Seed Generator (AI-4016 GigBid Phase 1b Part 2).

Defines client schemas with public marketplace metrics and hidden hiring preferences.
Hidden preferences are strictly internal and NEVER returned by public API endpoints.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

INDUSTRIES = [
    "FinTech", "HealthTech", "LegalTech", "SaaS", "E-Commerce", "Logistics",
    "EdTech", "CyberSec", "Manufacturing", "Retail", "DevTools", "CleanTech",
    "PropTech", "Gaming", "Telecom", "Media", "Hospitality", "BioTech"
]

COUNTRIES = [
    "United States", "United Kingdom", "Canada", "Germany", "Australia",
    "Netherlands", "Singapore", "France", "Switzerland", "Sweden", "Ireland"
]

COMPANY_PREFIXES = [
    "Apex", "Nexus", "Veritas", "Quantum", "Stratum", "Vanguard", "Pinnacle",
    "Helios", "Aura", "Nova", "Cipher", "Synapse", "Pulse", "Orion", "Cortex",
    "Starlight", "Beacon", "Solas", "Kinetics", "Zenith", "Omni", "Element"
]

COMPANY_SUFFIXES = [
    "Labs", "Technologies", "Solutions", "AI", "Systems", "Analytics",
    "Digital", "Capital", "Health", "Interactive", "Software", "Networks",
    "Logistics", "Cloud", "Dynamics", "Holdings", "Media", "Security"
]

SKILLS_POOL = [
    "Python", "PyTorch", "FastAPI", "Docker", "pgvector", "LangChain",
    "Transformers", "TypeScript", "React", "Next.js", "Node.js", "Tailwind CSS",
    "PostgreSQL", "Redis", "SQL", "Snowflake", "dbt", "Power BI", "Tableau",
    "BigQuery", "AWS", "Stripe API", "Kafka", "ClickHouse", "Pandas"
]


class ClientPublic(BaseModel):
    """Public marketplace client profile visible to freelancers."""
    id: str
    company: str
    industry: str
    country: str
    payment_verified: bool
    total_spent: float
    hire_rate: float = Field(ge=0.0, le=1.0)
    avg_rating: float = Field(ge=0.0, le=5.0)
    jobs_posted: int
    review_count: int


class ClientHiddenPreferences(BaseModel):
    """Hidden client preferences used strictly by simulator evaluation engine."""
    must_have_skills: list[str]
    budget_ceiling: float
    dislikes_generic_openers: bool
    likes_metrics: bool
    min_specificity: float = Field(ge=0.0, le=1.0)


class Client(BaseModel):
    """Full client model combining public metrics and hidden evaluation preferences."""
    public: ClientPublic
    hidden: ClientHiddenPreferences

    def to_public_dict(self) -> dict[str, Any]:
        """Returns strictly public dictionary. Guarantees zero leakage of hidden preferences."""
        return self.public.model_dump()


def generate_seed_clients(count: int = 300, seed: int = 42) -> list[Client]:
    """Deterministically generates ~300 clients (seed=42).

    Includes ~35 poor-history / high-risk clients (unverified payment, 0 spent, low rating)
    that link to scam and high-risk postings.
    """
    rng = random.Random(seed)
    clients: list[Client] = []

    # Designate ~35 poor-history clients (~12% of client pool)
    num_poor_history = 35

    for i in range(count):
        cid = f"client_{i+1:03d}"
        prefix = COMPANY_PREFIXES[i % len(COMPANY_PREFIXES)]
        suffix = COMPANY_SUFFIXES[(i // len(COMPANY_PREFIXES)) % len(COMPANY_SUFFIXES)]
        company = f"{prefix} {suffix} {i+1}"
        industry = rng.choice(INDUSTRIES)
        country = rng.choice(COUNTRIES)

        is_poor_history = i < num_poor_history

        if is_poor_history:
            payment_verified = rng.random() < 0.15  # mostly unverified
            total_spent = float(rng.choice([0, 0, 0, 50, 120]))
            hire_rate = float(round(rng.uniform(0.0, 0.25), 2))
            avg_rating = float(round(rng.uniform(1.5, 3.4), 1)) if total_spent > 0 else 0.0
            jobs_posted = rng.randint(1, 12)
            review_count = rng.randint(0, 2)
            budget_ceiling = float(rng.randint(100, 800))
            dislikes_generic = False  # scams don't care about quality
            likes_metrics = False
            min_specificity = 0.1
            must_skills = rng.sample(SKILLS_POOL, k=2)
        else:
            payment_verified = rng.random() < 0.94  # 94% verified
            total_spent = float(rng.choice([
                rng.randint(2500, 10000),
                rng.randint(10000, 50000),
                rng.randint(50000, 250000)
            ]))
            hire_rate = float(round(rng.uniform(0.60, 0.95), 2))
            avg_rating = float(round(rng.uniform(4.5, 5.0), 1))
            jobs_posted = rng.randint(8, 140)
            review_count = round(jobs_posted * hire_rate * rng.uniform(0.7, 0.95))
            budget_ceiling = float(rng.randint(2000, 18000))
            dislikes_generic = rng.random() < 0.85  # established clients dislike spam
            likes_metrics = rng.random() < 0.80     # established clients appreciate metrics
            min_specificity = float(round(rng.uniform(0.5, 0.85), 2))
            must_skills = rng.sample(SKILLS_POOL, k=rng.randint(2, 4))

        client_obj = Client(
            public=ClientPublic(
                id=cid,
                company=company,
                industry=industry,
                country=country,
                payment_verified=payment_verified,
                total_spent=total_spent,
                hire_rate=hire_rate,
                avg_rating=avg_rating,
                jobs_posted=jobs_posted,
                review_count=review_count,
            ),
            hidden=ClientHiddenPreferences(
                must_have_skills=must_skills,
                budget_ceiling=budget_ceiling,
                dislikes_generic_openers=dislikes_generic,
                likes_metrics=likes_metrics,
                min_specificity=min_specificity,
            ),
        )
        clients.append(client_obj)

    return clients


def save_seed_clients(output_path: Path, count: int = 300, seed: int = 42) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clients = generate_seed_clients(count=count, seed=seed)
    records = [c.model_dump() for c in clients]
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"[clients] Saved {len(records)} seed clients to {output_path}")


def load_seed_clients(file_path: Path) -> list[Client]:
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return [Client.model_validate(r) for r in raw]


if __name__ == "__main__":
    seed_file = Path(__file__).resolve().parent / "seed" / "clients.json"
    save_seed_clients(seed_file)
