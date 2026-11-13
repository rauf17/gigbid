"""Client Data Model and Seed Generator (AI-4016 GigBid Phase 1b Part 2).

Defines client schemas with public marketplace metrics and hidden hiring preferences.
Hidden preferences are strictly internal and NEVER returned by public API endpoints.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from datetime import datetime
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


GENERIC_OPENERS = [
    "i am excited to apply",
    "dear sir",
    "dear hiring manager",
    "dear client",
    "i am writing to apply",
    "very interested in your job posting",
    "100% job success",
    "hire me and i will get started",
    "lowest price, 24/7 support",
    "hello sir",
    "respected sir",
    "i have read your job description carefully",
    "i am an expert in",
    "look no further",
    "i can do this project perfectly",
]

SCAM_REPLIES = [
    "Hi! We were impressed by your proposal. Please message our project manager directly on Telegram @techlead_hiring or WhatsApp +1-555-0192 for the full specifications and escrow-free USDT milestone payment.",
    "Great proposal! Before awarding the contract, please contact our team on Telegram @project_desk to complete a quick test task.",
    "We would love to move forward immediately! To bypass platform fees and expedite setup, ping me directly on WhatsApp +1-555-0188.",
]

REQUIREMENT_QUESTIONS = [
    "Thanks for your detailed proposal. Could you elaborate on your experience with {skills}? Specifically, have you built systems with similar throughput in production?",
    "Hi! We're interested in your background. Can you share more details on how you would architect the pipeline for {company}?",
    "Thank you for applying. We noticed your work in {industry}. Do you have benchmark numbers or latency metrics from comparable projects?",
]

PRICE_NEGOTIATIONS = [
    "Thanks for submitting! We like your profile, but our budget ceiling for this milestone is closer to ${negotiated_amount}. Would you be willing to adjust your rate?",
    "We reviewed your proposal and think you'd be a great fit. However, your bid of ${bid_amount} is slightly above our allocated budget. Can we settle on ${negotiated_amount}?",
]

INTERVIEW_REQUESTS = [
    "Hi! We reviewed your proposal and case studies for {company} and were very impressed. Are you available for a 30-minute technical discussion tomorrow or later this week?",
    "Hello! Your background aligns closely with what we need for this project. When would you be free for a brief introductory call with our engineering team?",
]

HIRED_MESSAGES = [
    "Congratulations! We have accepted your proposal for {company}. We have funded the initial milestone and are excited to begin.",
    "We are thrilled to work with you on this project! The milestone contract has been created. Let's schedule our kickoff sync.",
]


class ProposalEvaluation(BaseModel):
    """Result of deterministic proposal evaluation by client decision engine."""
    status: str  # "ignored", "viewed", "replied", "interview", "hired"
    score: float
    feedback: str
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


def score_to_probabilities(score: float) -> dict[str, float]:
    """Maps composite proposal score in [0.0, 1.0] to probability distribution.

    Outcomes: ignored, viewed, replied, interview, hired.
    Higher scores monotonically shift weight from ignored/viewed towards replied/interview/hired.
    """
    s = max(0.0, min(1.0, score))
    w_ignored = math.exp(3.2 * (1.0 - s))
    w_viewed = math.exp(1.8 * (1.0 - abs(s - 0.40)))
    w_replied = math.exp(2.8 * s)
    w_interview = math.exp(4.2 * (s - 0.35)) if s >= 0.30 else 0.01
    w_hired = math.exp(5.5 * (s - 0.60)) if s >= 0.50 else 0.001

    total = w_ignored + w_viewed + w_replied + w_interview + w_hired
    return {
        "ignored": w_ignored / total,
        "viewed": w_viewed / total,
        "replied": w_replied / total,
        "interview": w_interview / total,
        "hired": w_hired / total,
    }


def generate_client_reply(
    outcome: str,
    client_public: dict[str, Any] | None,
    job: dict[str, Any],
    proposal: dict[str, Any],
    is_scam: bool = False,
    rng: random.Random | None = None,
) -> tuple[str, str | None]:
    """Generates deterministic client feedback and initial conversation message from templates."""
    if rng is None:
        rng = random.Random(42)

    company = (client_public or {}).get("company") or job.get("company") or "our company"
    industry = (client_public or {}).get("industry") or "technology"
    skills_list = job.get("skills") or ["the required technologies"]
    if isinstance(skills_list, str):
        try:
            skills_list = json.loads(skills_list)
        except (json.JSONDecodeError, TypeError, ValueError):
            skills_list = [skills_list]
    skills_str = ", ".join(skills_list[:2]) if skills_list else "required technologies"

    bid_amount = float(proposal.get("bid_amount", 1000.0))
    negotiated_amount = round(bid_amount * 0.85, 2)

    if outcome == "ignored":
        return ("Proposal archived without client review.", None)

    if outcome == "viewed":
        return ("Proposal viewed by client; no preliminary response sent.", None)

    if outcome in {"replied", "interview"}:
        if is_scam:
            template = rng.choice(SCAM_REPLIES)
            msg = template
            return ("Scam lead attempted off-platform diversion.", msg)

        if outcome == "interview":
            template = rng.choice(INTERVIEW_REQUESTS)
            msg = template.format(company=company)
            return ("Strong candidate profile; invited to technical interview.", msg)

        # outcome == "replied"
        # 40% probability price negotiation if bid > 500, else requirement question
        if bid_amount > 500 and rng.random() < 0.40:
            template = rng.choice(PRICE_NEGOTIATIONS)
            msg = template.format(bid_amount=bid_amount, negotiated_amount=negotiated_amount)
            return ("Client requested price negotiation before contract creation.", msg)
        else:
            template = rng.choice(REQUIREMENT_QUESTIONS)
            msg = template.format(skills=skills_str, company=company, industry=industry)
            return ("Client requested clarification on requirements and stack experience.", msg)

    if outcome == "hired":
        template = rng.choice(HIRED_MESSAGES)
        msg = template.format(company=company)
        return ("Proposal accepted; client funded milestone contract.", msg)

    return ("Proposal evaluated.", None)


def evaluate_proposal(
    proposal: dict[str, Any],
    client_hidden: dict[str, Any],
    job: dict[str, Any],
    client_public: dict[str, Any] | None = None,
    is_scam: bool = False,
    client_llm: bool = False,
) -> ProposalEvaluation:
    """Deterministically evaluates a submitted proposal against client hidden preferences.

    Scoring factors:
      1. overlap with must_have_skills (weight 0.30)
      2. specificity: mentions concrete project and metric (weight 0.25)
      3. generic-opener detection (penalty up to -0.25)
      4. bid vs budget ceiling (bonus if <= ceiling, progressive penalty if over)
      5. response turnaround speed (bonus if submitted shortly after job posting)

    Seeded per proposal ID for exact repeatability.
    Optional client_llm hook (OFF by default, raises NotImplementedError when True).
    """
    if client_llm:
        raise NotImplementedError("client_llm hook is disabled; running in deterministic simulation mode.")

    proposal_id = str(proposal.get("id", "prop_seed"))
    seed = int(hashlib.sha256(proposal_id.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    cover = str(proposal.get("cover_letter", "")).lower()
    screening = proposal.get("screening_answers")
    screening_str = json.dumps(screening).lower() if screening else ""
    full_text = f"{cover} {screening_str}"

    # 1. Overlap of proposal text with must_have_skills
    must_skills = [s.lower() for s in client_hidden.get("must_have_skills", [])]
    if must_skills:
        matched_count = sum(1 for s in must_skills if re.search(rf"\b{re.escape(s)}\b", full_text))
        overlap_ratio = matched_count / len(must_skills)
    else:
        overlap_ratio = 1.0
    overlap_score = overlap_ratio * 0.30

    # 2. Specificity: concrete project and metric
    has_metric = bool(re.search(
        r"\b\d+%\b|\$\d+[\d,]*|\b\d+(\.\d+)?\s*(ms|s|x|gb|tb|k|m|users|qps|req/s)\b|\b(reduced|increased|improved|boosted|saved|scaled|optimized)\b.*\b\d+",
        full_text
    ))
    has_project = bool(re.search(
        r"\b(project|pipeline|architecture|database|infrastructure|microservice|model|engine|system|dataset|platform|warehouse|fastapi|react|postgres|docker)\b",
        full_text
    ))

    if has_project and has_metric:
        spec_val = 1.0
    elif has_project or has_metric:
        spec_val = 0.5
    else:
        spec_val = 0.1

    spec_score = spec_val * 0.25
    if client_hidden.get("likes_metrics", False):
        spec_score += 0.05 if has_metric else -0.10
    if spec_val < client_hidden.get("min_specificity", 0.0):
        spec_score -= 0.10

    # 3. Generic-opener detection
    is_generic = any(phrase in full_text for phrase in GENERIC_OPENERS)
    if is_generic:
        generic_score = -0.25 if client_hidden.get("dislikes_generic_openers", True) else -0.10
    else:
        generic_score = 0.05

    # 4. Bid vs Budget Ceiling
    bid_amount = float(proposal.get("bid_amount", 1000.0))
    budget_ceiling = float(client_hidden.get("budget_ceiling", 5000.0))
    if budget_ceiling <= 0:
        budget_ceiling = 1000.0

    if bid_amount <= budget_ceiling:
        budget_score = 0.15
    else:
        overrun = (bid_amount - budget_ceiling) / budget_ceiling
        budget_score = -0.25 * min(2.0, overrun)

    # 5. Turnaround speed (how fast freelancer bid after posting)
    posted_at_str = job.get("posted_at")
    submitted_at_str = proposal.get("submitted_at")
    speed_score = 0.05
    if posted_at_str and submitted_at_str:
        try:
            t_post = datetime.fromisoformat(posted_at_str)
            t_sub = datetime.fromisoformat(submitted_at_str)
            delta_hours = max(0.0, (t_sub - t_post).total_seconds() / 3600.0)
            if delta_hours <= 12.0:
                speed_score = 0.10
            elif delta_hours <= 36.0:
                speed_score = 0.05
            elif delta_hours <= 72.0:
                speed_score = 0.0
            else:
                speed_score = -0.05
        except (ValueError, TypeError):
            speed_score = 0.05

    # Composite Score
    base_score = 0.15
    raw_score = base_score + overlap_score + spec_score + generic_score + budget_score + speed_score
    score = max(0.0, min(1.0, round(raw_score, 3)))

    # Probability Mapping & Outcome Sampling
    probs = score_to_probabilities(score)
    outcomes = ["ignored", "viewed", "replied", "interview", "hired"]
    weights = [probs[o] for o in outcomes]
    chosen_outcome = rng.choices(outcomes, weights=weights, k=1)[0]

    feedback, message = generate_client_reply(
        outcome=chosen_outcome,
        client_public=client_public,
        job=job,
        proposal=proposal,
        is_scam=is_scam,
        rng=rng,
    )

    return ProposalEvaluation(
        status=chosen_outcome,
        score=score,
        feedback=feedback,
        message=message,
        details={
            "overlap_score": round(overlap_score, 3),
            "specificity_score": round(spec_score, 3),
            "generic_score": round(generic_score, 3),
            "budget_score": round(budget_score, 3),
            "speed_score": round(speed_score, 3),
            "probabilities": {k: round(v, 4) for k, v in probs.items()},
        },
    )


if __name__ == "__main__":
    seed_file = Path(__file__).resolve().parent / "seed" / "clients.json"
    save_seed_clients(seed_file)
