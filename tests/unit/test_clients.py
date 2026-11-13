"""Unit tests for client seed data and preferences (AI-4016 GigBid Phase 1b Part 2).

Validates client schemas, hidden preference isolation, and job-to-client linkage.
"""
from __future__ import annotations

import json
from pathlib import Path

from gigsim.clients import (
    Client,
    evaluate_proposal,
    load_seed_clients,
    score_to_probabilities,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEED_CLIENTS_FILE = REPO_ROOT / "gigsim" / "seed" / "clients.json"
HISTORICAL_JOBS_FILE = REPO_ROOT / "data" / "processed" / "jobs_historical.jsonl"
STREAM_JOBS_FILE = REPO_ROOT / "data" / "processed" / "jobs_stream.jsonl"
GOLD_LABELS_FILE = REPO_ROOT / "data" / "processed" / "jobs_gold_labels.jsonl"


def test_seed_clients_file_and_counts():
    assert SEED_CLIENTS_FILE.exists(), f"Missing seed clients: {SEED_CLIENTS_FILE}"
    clients = load_seed_clients(SEED_CLIENTS_FILE)
    assert 280 <= len(clients) <= 320, f"Expected ~300 clients, got {len(clients)}"


def test_client_schema_and_hidden_preferences():
    clients = load_seed_clients(SEED_CLIENTS_FILE)
    client_ids = set()

    for c in clients:
        assert isinstance(c, Client)
        pub = c.public
        hidden = c.hidden

        client_ids.add(pub.id)
        assert len(pub.company) > 0
        assert len(pub.industry) > 0
        assert 0.0 <= pub.hire_rate <= 1.0
        assert 0.0 <= pub.avg_rating <= 5.0
        assert pub.jobs_posted >= 0
        assert pub.review_count >= 0

        # Hidden preferences
        assert 2 <= len(hidden.must_have_skills) <= 4
        assert hidden.budget_ceiling > 0
        assert isinstance(hidden.dislikes_generic_openers, bool)
        assert isinstance(hidden.likes_metrics, bool)
        assert 0.0 <= hidden.min_specificity <= 1.0

        # Test to_public_dict isolation
        pub_dict = c.to_public_dict()
        assert "must_have_skills" not in pub_dict
        assert "budget_ceiling" not in pub_dict
        assert "dislikes_generic_openers" not in pub_dict
        assert "likes_metrics" not in pub_dict
        assert "min_specificity" not in pub_dict
        assert "hidden" not in pub_dict

    assert len(client_ids) == len(clients), "Client IDs must be unique"


def test_every_job_references_a_valid_client():
    clients = load_seed_clients(SEED_CLIENTS_FILE)
    valid_cids = {c.public.id for c in clients}

    hist_jobs = [json.loads(l) for l in HISTORICAL_JOBS_FILE.read_text(encoding="utf-8").strip().splitlines()]
    stream_jobs = [json.loads(l) for l in STREAM_JOBS_FILE.read_text(encoding="utf-8").strip().splitlines()]

    for j in hist_jobs:
        assert "client_id" in j, f"Historical job {j['id']} missing client_id"
        assert j["client_id"] in valid_cids, f"Invalid client_id {j['client_id']} in job {j['id']}"

    for j in stream_jobs:
        assert "client_id" in j, f"Stream job {j['id']} missing client_id"
        assert j["client_id"] in valid_cids, f"Invalid client_id {j['client_id']} in job {j['id']}"


def test_scam_jobs_tied_to_poor_history_clients():
    clients = load_seed_clients(SEED_CLIENTS_FILE)
    client_map = {c.public.id: c.public for c in clients}

    stream_jobs = {j["id"]: j for j in [json.loads(l) for l in STREAM_JOBS_FILE.read_text(encoding="utf-8").strip().splitlines()]}
    labels = [json.loads(l) for l in GOLD_LABELS_FILE.read_text(encoding="utf-8").strip().splitlines()]

    scam_jobs = [stream_jobs[l["id"]] for l in labels if l["is_scam"]]
    assert len(scam_jobs) > 0, "No scam jobs found in labels"

    poor_history_scams = 0
    for j in scam_jobs:
        client = client_map[j["client_id"]]
        # Poor history: unverified payment OR 0 spent OR low rating (< 3.5)
        if not client.payment_verified or client.total_spent < 500 or client.avg_rating < 3.5:
            poor_history_scams += 1

    ratio = poor_history_scams / len(scam_jobs)
    assert ratio >= 0.80, f"Expected >= 80% scam jobs tied to poor-history clients, got {ratio:.1%}"


def test_evaluate_proposal_high_quality_vs_generic():
    client_hidden = {
        "must_have_skills": ["Python", "FastAPI", "pgvector"],
        "budget_ceiling": 2500.0,
        "dislikes_generic_openers": True,
        "likes_metrics": True,
        "min_specificity": 0.5,
    }
    client_public = {"company": "Nexus Labs", "industry": "FinTech"}
    job = {
        "title": "Build FastAPI pgvector Search",
        "description": "Looking for an expert to build high-scale semantic search.",
        "skills": ["Python", "FastAPI", "pgvector"],
        "posted_at": "2026-10-01T10:00:00Z",
    }

    # High quality proposal
    good_prop = {
        "id": "prop_high_quality_1",
        "cover_letter": "Architected a pgvector retrieval pipeline on FastAPI that scaled to 3.5M documents, improving latency by 45% and achieving 99.2% accuracy.",
        "bid_amount": 1800.0,
        "submitted_at": "2026-10-01T12:00:00Z",
    }
    good_res = evaluate_proposal(good_prop, client_hidden, job, client_public)
    assert good_res.score >= 0.70
    assert good_res.status in {"replied", "interview", "hired"}
    assert good_res.message is not None

    # Generic proposal
    bad_prop = {
        "id": "prop_bad_generic_1",
        "cover_letter": "Dear sir, I am excited to apply for your project. I have 100% job success and lowest price. Hire me and I will get started.",
        "bid_amount": 3500.0,  # exceeds ceiling
        "submitted_at": "2026-10-06T12:00:00Z",  # 5 days late
    }
    bad_res = evaluate_proposal(bad_prop, client_hidden, job, client_public)
    assert bad_res.score < 0.40
    assert bad_res.status in {"ignored", "viewed"}


def test_evaluate_proposal_deterministic_seeding():
    client_hidden = {
        "must_have_skills": ["TypeScript", "React"],
        "budget_ceiling": 1500.0,
        "dislikes_generic_openers": True,
        "likes_metrics": True,
        "min_specificity": 0.4,
    }
    job = {"posted_at": "2026-10-01T10:00:00Z"}
    prop = {
        "id": "prop_repeatable_42",
        "cover_letter": "Developed Next.js portal serving 50k DAU with 99.9% uptime using React and TypeScript.",
        "bid_amount": 1200.0,
        "submitted_at": "2026-10-01T14:00:00Z",
    }

    res1 = evaluate_proposal(prop, client_hidden, job)
    res2 = evaluate_proposal(prop, client_hidden, job)

    assert res1.status == res2.status
    assert res1.score == res2.score
    assert res1.feedback == res2.feedback
    assert res1.message == res2.message
    assert res1.details == res2.details


def test_evaluate_proposal_client_llm_hook_disabled():
    import pytest
    with pytest.raises(NotImplementedError, match="client_llm hook is disabled"):
        evaluate_proposal(
            proposal={"id": "prop_test"},
            client_hidden={},
            job={},
            client_llm=True
        )


def test_evaluate_proposal_scam_lead_template():
    client_hidden = {"must_have_skills": ["Python"], "budget_ceiling": 500.0}
    job = {"posted_at": "2026-10-01T10:00:00Z"}
    prop = {
        "id": "prop_scam_test",
        "cover_letter": "Python developer with high throughput metrics 95%.",
        "bid_amount": 400.0,
        "submitted_at": "2026-10-01T11:00:00Z",
    }
    res = evaluate_proposal(prop, client_hidden, job, is_scam=True)
    if res.status in {"replied", "interview"}:
        assert any(k in res.message.lower() for k in ["telegram", "whatsapp", "crypto", "usdt"])


def test_score_to_probabilities_monotonicity():
    probs_low = score_to_probabilities(0.1)
    probs_high = score_to_probabilities(0.9)

    assert probs_low["ignored"] > probs_high["ignored"]
    assert probs_high["interview"] > probs_low["interview"]
    assert probs_high["hired"] > probs_low["hired"]
    assert abs(sum(probs_low.values()) - 1.0) < 1e-4
    assert abs(sum(probs_high.values()) - 1.0) < 1e-4

