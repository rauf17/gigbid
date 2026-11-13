"""Unit tests for client seed data and preferences (AI-4016 GigBid Phase 1b Part 2).

Validates client schemas, hidden preference isolation, and job-to-client linkage.
"""
from __future__ import annotations

import json
from pathlib import Path

from gigsim.clients import Client, load_seed_clients

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
