"""Unit and tenant isolation tests for authentication, profiles, and marketplace connections."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.auth.service import get_marketplace_token
from apps.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("REVIEWER_EMAIL", "reviewer_test@gigbid.local")
    monkeypatch.setenv("REVIEWER_PASSWORD", "ReviewerPass123!")
    app = create_app()
    with TestClient(app) as tc:
        yield tc


def test_auth_register_and_login_flow(client: TestClient) -> None:
    test_email = f"user_{uuid4().hex[:8]}@example.com"
    # 1. Register User A
    res = client.post(
        "/auth/register",
        json={"email": test_email, "password": "password123", "persona_id": "ai_ml"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert res.cookies.get("access_token") is not None
    token_a = data["access_token"]

    # 2. Get /auth/me with Bearer token
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert res_me.status_code == 200
    user_a = res_me.json()
    assert user_a["email"] == test_email
    assert user_a["persona_id"] == "ai_ml"

    # 3. Duplicate registration rejected
    res_dup = client.post(
        "/auth/register",
        json={"email": test_email, "password": "password456"},
    )
    assert res_dup.status_code == 400

    # 4. Login with correct password
    res_login = client.post(
        "/auth/login",
        json={"email": test_email, "password": "password123"},
    )
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

    # 5. Login with wrong password rejected
    res_wrong = client.post(
        "/auth/login",
        json={"email": test_email, "password": "wrongpassword"},
    )
    assert res_wrong.status_code == 401


def test_tenant_isolation_profile_and_connections(client: TestClient) -> None:
    email_a = f"tenant_a_{uuid4().hex[:8]}@example.com"
    email_b = f"tenant_b_{uuid4().hex[:8]}@example.com"

    # Register User A and User B
    res_a = client.post(
        "/auth/register",
        json={"email": email_a, "password": "password123", "persona_id": "ai_ml"},
    )
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]

    res_b = client.post(
        "/auth/register",
        json={"email": email_b, "password": "password123", "persona_id": "fullstack"},
    )
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]

    # User A updates profile
    update_res = client.put(
        "/profile",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"hourly_rate": 85.0, "weekly_connects_budget": 60},
    )
    assert update_res.status_code == 200
    prof_a = update_res.json()
    assert prof_a["hourly_rate"] == 85.0
    assert prof_a["weekly_connects_budget"] == 60

    # User B gets their profile - must NOT see User A's updates
    prof_b_res = client.get("/profile", headers={"Authorization": f"Bearer {token_b}"})
    assert prof_b_res.status_code == 200
    prof_b = prof_b_res.json()
    assert prof_b["hourly_rate"] == 50.0  # default
    assert prof_b["persona_id"] == "fullstack"
    assert prof_b["user_id"] != prof_a["user_id"]

    # User A connects marketplace token
    conn_res = client.post(
        "/connections/marketplace",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"token": "super_secret_gigsim_key_12345"},
    )
    assert conn_res.status_code == 200
    # The response must NEVER return the token!
    assert "super_secret" not in conn_res.text
    assert conn_res.json()["status"] == "connected"

    # Verify token is encrypted in DB/store and recoverable only internally
    decrypted = get_marketplace_token(prof_a["user_id"])
    assert decrypted == "super_secret_gigsim_key_12345"

    # User B has no marketplace token
    assert get_marketplace_token(prof_b["user_id"]) is None


def test_reviewer_seeded_on_startup(client: TestClient) -> None:
    res_login = client.post(
        "/auth/login",
        json={"email": "reviewer_test@gigbid.local", "password": "ReviewerPass123!"},
    )
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]

    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "reviewer_test@gigbid.local"
    assert res_me.json()["persona_id"] == "ai_ml"
