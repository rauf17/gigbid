"""Integration tests for student-built GigSim API (AI-4016 GigBid Phase 1b Part 5).

Validates end-to-end integration requirements:
  - Auth required when token is set
  - Idempotent submit charges Connects exactly once
  - Dry run charges zero Connects
  - Rate limiter returns 429 past 30 req/min with Retry-After header
  - Tick releases jobs and advances simulated time
  - Hidden client preferences never leak into any public response
  - Seeded determinism produces exact matching outcomes across runs
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gigsim.app import app
from gigsim.seed import get_db_connection, reset_database


@pytest.fixture(autouse=True)
def setup_sim_environment():
    """Resets simulator database and isolates testing environment."""
    os.environ["GIGSIM_TESTING"] = "1"
    os.environ["GIGSIM_FAULT_RATE"] = "0.0"
    os.environ.pop("GIGSIM_TEST_RATE_LIMIT", None)
    os.environ.pop("GIGSIM_API_TOKEN", None)
    conn = get_db_connection()
    reset_database(conn)
    yield
    os.environ.pop("GIGSIM_API_TOKEN", None)
    os.environ.pop("GIGSIM_TEST_RATE_LIMIT", None)
    os.environ["GIGSIM_TESTING"] = "1"


def test_auth_required():
    """Verify that requests require valid Bearer token authentication when configured."""
    secret = "integ-secret-token-xyz"
    os.environ["GIGSIM_API_TOKEN"] = secret

    with TestClient(app) as client:
        # Public health check is exempt
        resp_health = client.get("/health")
        assert resp_health.status_code == 200

        # Protected endpoints require auth
        resp_no_auth = client.get("/jobs")
        assert resp_no_auth.status_code == 401
        assert "Bearer" in resp_no_auth.json()["detail"]

        resp_bad_auth = client.get("/jobs", headers={"Authorization": "Bearer wrong-token"})
        assert resp_bad_auth.status_code == 401
        assert "Invalid API token" in resp_bad_auth.json()["detail"]

        resp_good_auth = client.get("/jobs", headers={"Authorization": f"Bearer {secret}"})
        assert resp_good_auth.status_code == 200


def test_idempotent_submit_charges_connects_once():
    """Verify idempotent submit spends Connects once and returns cached response on retry."""
    with TestClient(app) as client:
        jobs = client.get("/jobs").json()["items"]
        job_id = jobs[0]["id"]
        job_cost = jobs[0]["connects_cost"]

        # Create proposal draft
        prop_payload = {
            "job_id": job_id,
            "cover_letter": "Production-tested engineer with verified latency benchmarks under 50ms.",
            "bid_amount": 1200.0,
            "dry_run": False,
        }
        prop_id = client.post("/proposals", json=prop_payload).json()["id"]

        init_balance = client.get("/connects/balance").json()["balance"]
        assert init_balance == 150

        # First submission with idempotency key
        headers = {"Idempotency-Key": "integ-sub-key-1"}
        resp1 = client.post(f"/proposals/{prop_id}/submit", headers=headers)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "submitted"
        expected_balance = init_balance - job_cost
        assert data1["connects_balance"] == expected_balance

        # Verify current balance
        cur_balance = client.get("/connects/balance").json()["balance"]
        assert cur_balance == expected_balance

        # Repeat submission with identical idempotency key
        resp2 = client.post(f"/proposals/{prop_id}/submit", headers=headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2 == data1

        # Connects must not be deducted a second time
        final_balance = client.get("/connects/balance").json()["balance"]
        assert final_balance == expected_balance


def test_dry_run_charges_nothing():
    """Verify proposal dry_run returns exact preview and cost without balance deduction or DB commit."""
    with TestClient(app) as client:
        jobs = client.get("/jobs").json()["items"]
        job_id = jobs[0]["id"]

        prop_payload = {
            "job_id": job_id,
            "cover_letter": "Dry run preview test.",
            "bid_amount": 800.0,
            "dry_run": True,
        }
        resp = client.post("/proposals", json=prop_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["status"] == "draft"
        assert data["connects_cost"] > 0

        # Balance remains unmodified
        balance = client.get("/connects/balance").json()["balance"]
        assert balance == 150

        # Proposals list has no submitted proposals
        submitted_props = client.get("/proposals?status=submitted").json()
        assert len(submitted_props) == 0


def test_rate_limit_429_past_limit():
    """Verify sliding-window rate limiter returns 429 with Retry-After header when limit exceeded."""
    os.environ["GIGSIM_TEST_RATE_LIMIT"] = "1"

    try:
        with TestClient(app) as client:
            got_429 = False
            retry_after_val = None

            # Platform limit is 30 requests per minute
            for _ in range(35):
                resp = client.get("/jobs")
                if resp.status_code == 429:
                    got_429 = True
                    retry_after_val = resp.headers.get("Retry-After")
                    break

            assert got_429, "Expected 429 Too Many Requests after 30 requests within 1 minute"
            assert retry_after_val is not None
            assert int(retry_after_val) > 0
    finally:
        os.environ.pop("GIGSIM_TEST_RATE_LIMIT", None)


def test_tick_releases_jobs_and_advances_time():
    """Verify /admin/tick releases n jobs and advances simulated time by 24h per tick."""
    with TestClient(app) as client:
        health_initial = client.get("/health").json()
        initial_count = health_initial["released_jobs_count"]
        initial_time = health_initial["simulated_time"]

        resp_tick = client.post("/admin/tick?n=7")
        assert resp_tick.status_code == 200
        tick_data = resp_tick.json()

        assert tick_data["released_jobs"] == 7
        assert tick_data["total_released"] == initial_count + 7

        health_after = client.get("/health").json()
        assert health_after["released_jobs_count"] == initial_count + 7

        # Verify time advancement by exactly 24 hours
        t1 = datetime.fromisoformat(initial_time)
        t2 = datetime.fromisoformat(health_after["simulated_time"])
        assert (t2 - t1).total_seconds() == 86400.0


def test_hidden_fields_never_appear_in_any_response():
    """Verify zero leakage of client hidden evaluation preferences across all public endpoints."""
    forbidden_keys = {
        "must_have_skills",
        "budget_ceiling",
        "dislikes_generic_openers",
        "likes_metrics",
        "min_specificity",
        "hidden_json",
        "hidden",
    }

    def assert_no_forbidden_keys(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in forbidden_keys, f"Found forbidden hidden key '{k}' at {path}.{k}"
                assert_no_forbidden_keys(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                assert_no_forbidden_keys(item, f"{path}[{i}]")

    with TestClient(app) as client:
        # Check /clients/{id} for multiple clients
        for i in range(1, 15):
            cid = f"client_{i:03d}"
            resp = client.get(f"/clients/{cid}")
            assert resp.status_code == 200
            assert_no_forbidden_keys(resp.json(), f"/clients/{cid}")

        # Check /jobs and /jobs/{id}
        jobs_resp = client.get("/jobs?limit=20").json()
        assert_no_forbidden_keys(jobs_resp, "/jobs")
        first_job_id = jobs_resp["items"][0]["id"]
        job_detail = client.get(f"/jobs/{first_job_id}").json()
        assert_no_forbidden_keys(job_detail, f"/jobs/{first_job_id}")

        # Check /proposals
        props_resp = client.get("/proposals").json()
        assert_no_forbidden_keys(props_resp, "/proposals")

        # Check /conversations
        convs_resp = client.get("/conversations").json()
        assert_no_forbidden_keys(convs_resp, "/conversations")


def test_same_seed_gives_same_outcomes():
    """Verify deterministic repeatability: same inputs and proposal ID produce exact identical outcomes."""
    def run_simulation() -> dict[str, Any]:
        conn = get_db_connection()
        reset_database(conn)
        with TestClient(app) as client:
            job_id = client.get("/jobs").json()["items"][0]["id"]
            payload = {
                "id": "prop_repeat_integ_42",
                "job_id": job_id,
                "cover_letter": "Architected a scalable pgvector pipeline with 45ms latency and 98% recall.",
                "bid_amount": 1500.0,
                "dry_run": False,
            }
            resp_prop = client.post("/proposals", json=payload)
            assert resp_prop.status_code == 200
            resp_sub = client.post(f"/proposals/{payload['id']}/submit")
            assert resp_sub.status_code == 200
            resp_tick = client.post("/admin/tick?n=5")
            assert resp_tick.status_code == 200

            props = client.get("/proposals").json()
            assert isinstance(props, list)
            target = next(p for p in props if p["id"] == payload["id"])
            convs = client.get("/conversations").json()
            messages = []
            if convs:
                messages = client.get(f"/conversations/{convs[0]['id']}/messages").json()

            return {
                "status": target["status"],
                "client_feedback": target["client_feedback"],
                "messages": [m["text"] for m in messages],
            }

    run_a = run_simulation()
    run_b = run_simulation()

    assert run_a == run_b, f"Expected deterministic outcomes to match: {run_a} != {run_b}"
