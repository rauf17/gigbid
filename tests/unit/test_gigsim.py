"""Unit tests for student-built GigSim API (AI-4016 GigBid Phase 1b Part 3).

Validates all required endpoints, public field isolation, idempotency keys,
connects deduction, proposal dry runs, simulation ticks, and administrative reset.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gigsim.app import app
from gigsim.seed import get_db_connection, reset_database

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def reset_sim_state():
    """Resets simulator database before each test."""
    conn = get_db_connection()
    reset_database(conn)
    yield


@pytest.fixture
def client():
    # Disable fault injection during functional endpoint tests
    os.environ["GIGSIM_TESTING"] = "1"
    orig_token = os.environ.get("GIGSIM_API_TOKEN")
    if "GIGSIM_API_TOKEN" in os.environ:
        del os.environ["GIGSIM_API_TOKEN"]

    with TestClient(app) as test_client:
        yield test_client

    if orig_token is not None:
        os.environ["GIGSIM_API_TOKEN"] = orig_token
    del os.environ["GIGSIM_TESTING"]


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["connects_balance"] == 150
    assert data["released_jobs_count"] >= 15


def test_jobs_list_and_filters(client: TestClient):
    # Initial batch
    resp = client.get("/jobs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 10
    assert data["total"] >= 15

    # Filter by category
    resp_cat = client.get("/jobs?category=AI/ML")
    assert resp_cat.status_code == 200
    for job in resp_cat.json()["items"]:
        assert job["category"] == "AI/ML"

    # Search filter
    resp_q = client.get("/jobs?q=engineer")
    assert resp_q.status_code == 200
    for job in resp_q.json()["items"]:
        assert "engineer" in job["title"].lower() or "engineer" in job["description"].lower()


def test_jobs_get_by_id(client: TestClient):
    resp = client.get("/jobs")
    first_job = resp.json()["items"][0]

    resp_single = client.get(f"/jobs/{first_job['id']}")
    assert resp_single.status_code == 200
    assert resp_single.json()["id"] == first_job["id"]

    # 404 on unreleased/non-existent
    resp_404 = client.get("/jobs/job_stream_99999")
    assert resp_404.status_code == 404


def test_clients_public_field_isolation(client: TestClient):
    resp = client.get("/clients/client_001")
    assert resp.status_code == 200
    data = resp.json()

    # Public fields present
    assert "id" in data
    assert "company" in data
    assert "industry" in data
    assert "payment_verified" in data
    assert "total_spent" in data
    assert "hire_rate" in data

    # Hidden fields NEVER exposed
    assert "must_have_skills" not in data
    assert "budget_ceiling" not in data
    assert "dislikes_generic_openers" not in data
    assert "likes_metrics" not in data
    assert "min_specificity" not in data
    assert "hidden" not in data


def test_connects_balance(client: TestClient):
    resp = client.get("/connects/balance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == 150
    assert data["currency"] == "connects"
    assert data["weekly_grant"] == 80


def test_proposal_dry_run_does_not_spend_connects(client: TestClient):
    job = client.get("/jobs").json()["items"][0]
    initial_balance = client.get("/connects/balance").json()["balance"]

    payload = {
        "job_id": job["id"],
        "cover_letter": "I have built a similar system delivering 95% accuracy.",
        "bid_amount": 1500.0,
        "dry_run": True
    }
    resp = client.post("/proposals", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["status"] == "draft"
    assert data["connects_cost"] == job["connects_cost"]

    # Connects balance unchanged
    after_balance = client.get("/connects/balance").json()["balance"]
    assert after_balance == initial_balance

    # No proposal stored in proposals list
    props = client.get("/proposals").json()
    assert not any(p["job_id"] == job["id"] for p in props)


def test_proposal_submit_idempotent_single_charge(client: TestClient):
    job = client.get("/jobs").json()["items"][0]
    initial_balance = client.get("/connects/balance").json()["balance"]

    # 1. Create draft proposal
    payload = {
        "job_id": job["id"],
        "cover_letter": "In my previous project for a FinTech client, I reduced latency by 45%.",
        "bid_amount": 1200.0,
        "dry_run": False
    }
    resp_draft = client.post("/proposals", json=payload)
    assert resp_draft.status_code == 200
    prop_id = resp_draft.json()["id"]
    assert resp_draft.json()["status"] == "draft"

    # Connects still not spent
    assert client.get("/connects/balance").json()["balance"] == initial_balance

    # 2. Submit proposal with Idempotency-Key
    headers = {"Idempotency-Key": "test-key-abc-123"}
    resp_submit = client.post(f"/proposals/{prop_id}/submit", headers=headers)
    assert resp_submit.status_code == 200
    sub_data = resp_submit.json()
    assert sub_data["status"] == "submitted"
    cost = sub_data["connects_cost"]
    expected_balance = initial_balance - cost
    assert sub_data["connects_balance"] == expected_balance

    # 3. Repeat call with SAME Idempotency-Key must return same result and NEVER double charge
    resp_repeat = client.post(f"/proposals/{prop_id}/submit", headers=headers)
    assert resp_repeat.status_code == 200
    repeat_data = resp_repeat.json()
    assert repeat_data["status"] == "submitted"
    assert repeat_data["connects_balance"] == expected_balance

    current_balance = client.get("/connects/balance").json()["balance"]
    assert current_balance == expected_balance


def test_admin_tick_and_proposal_evaluation(client: TestClient):
    job = client.get("/jobs").json()["items"][0]

    # Create and submit evidence-grounded proposal with metrics
    prop_payload = {
        "job_id": job["id"],
        "cover_letter": "Recently delivered a pgvector pipeline achieving sub-second latency on 4.5M pages with 91% accuracy.",
        "bid_amount": 1000.0,
        "dry_run": False
    }
    prop_id = client.post("/proposals", json=prop_payload).json()["id"]
    client.post(f"/proposals/{prop_id}/submit")

    # Tick simulation: release 5 jobs and advance time
    resp_tick = client.post("/admin/tick?n=5")
    assert resp_tick.status_code == 200
    tick_data = resp_tick.json()
    assert tick_data["released_jobs"] == 5
    assert tick_data["proposals_evaluated"] >= 1

    # Check that proposal advanced from 'submitted' to 'replied' or 'interview'
    proposals = client.get("/proposals").json()
    target_prop = next(p for p in proposals if p["id"] == prop_id)
    assert target_prop["status"] in {"replied", "interview", "viewed"}

    # If replied or interview, verify conversation was created
    if target_prop["status"] in {"replied", "interview"}:
        convs = client.get("/conversations").json()
        assert len(convs) >= 1
        conv_id = convs[0]["id"]

        # View messages
        msgs = client.get(f"/conversations/{conv_id}/messages").json()
        assert len(msgs) >= 1
        assert msgs[0]["sender"] == "client"

        # Reply to client message
        msg_payload = {"text": "Thank you! I am available for a call this Thursday at 2 PM UTC."}
        resp_msg = client.post(
            f"/conversations/{conv_id}/messages",
            json=msg_payload,
            headers={"Idempotency-Key": "msg-key-1"}
        )
        assert resp_msg.status_code == 200
        assert resp_msg.json()["sender"] == "freelancer"


def test_admin_reset(client: TestClient):
    # Perform some changes
    client.post("/admin/tick?n=10")
    resp_reset = client.post("/admin/reset")
    assert resp_reset.status_code == 200
    assert resp_reset.json()["status"] == "reset"

    # Verify reset to initial state
    health = client.get("/health").json()
    assert health["connects_balance"] == 150
    assert health["active_proposals_count"] == 0


def test_authentication_and_rate_limiting():
    # Test Bearer token requirement when GIGSIM_API_TOKEN is set
    os.environ["GIGSIM_API_TOKEN"] = "test-secret-token-123"
    try:
        with TestClient(app) as auth_client:
            # /health passes without auth
            resp_health = auth_client.get("/health")
            assert resp_health.status_code == 200

            # /jobs rejected without token
            resp_unauth = auth_client.get("/jobs")
            assert resp_unauth.status_code == 401

            # /jobs accepted with valid token
            headers = {"Authorization": "Bearer test-secret-token-123"}
            resp_auth = auth_client.get("/jobs", headers=headers)
            assert resp_auth.status_code == 200

            # Test rate limiting: 30 requests within 60s
            for _ in range(30):
                r = auth_client.get("/jobs", headers=headers)
                if r.status_code == 429:
                    break

            # Next request should be rate-limited (429)
            resp_limit = auth_client.get("/jobs", headers=headers)
            assert resp_limit.status_code == 429
            assert "Retry-After" in resp_limit.headers
    finally:
        del os.environ["GIGSIM_API_TOKEN"]
