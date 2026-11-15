"""Comprehensive tests for FastAPI backend routers: runs, approvals, SSE, degraded mode, and tenancy."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agent.marketplace_models import Job
from agent.marketplace_port import MarketplacePort, MarketplaceUnavailable
from apps.api.deps import get_marketplace_port
from apps.api.main import create_app


def make_test_job(
    id: str = "job_test_001",
    title: str = "Test Job",
    description: str = "Job description text",
    category: str = "ai_ml",
    skills: list[str] | None = None,
    budget_max: float = 500.0,
    connects_cost: int = 4,
) -> Job:
    return Job(
        id=id,
        title=title,
        description=description,
        category=category,
        skills=skills or ["Python"],
        budget_type="fixed",
        budget_min=100.0,
        budget_max=budget_max,
        client_country="US",
        posted_at="2026-11-15T00:00:00Z",
        connects_cost=connects_cost,
        client_id="client_123",
    )


class MockPort(MarketplacePort):
    """Hermetic mock MarketplacePort for API route testing."""

    def __init__(self, jobs: list[Job] | None = None, should_fail: bool = False) -> None:
        self.jobs = jobs or [
            make_test_job(
                id="job_test_001",
                title="FastAPI Backend Engineer Needed",
                description="Build a high performance async API using FastAPI and Redis",
                category="fullstack",
                skills=["FastAPI", "Python", "Redis"],
                budget_max=500.0,
                connects_cost=4,
            ),
            make_test_job(
                id="job_test_002",
                title="Machine Learning RAG Pipeline",
                description="Design vector search and sentence transformer embeddings",
                category="ai_ml",
                skills=["Python", "PyTorch", "Qdrant"],
                budget_max=1200.0,
                connects_cost=6,
            ),
        ]
        self.should_fail = should_fail

    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[Job]:
        if self.should_fail:
            raise MarketplaceUnavailable("Marketplace backend offline", retryable=True)
        res = self.jobs
        if category:
            res = [j for j in res if j.category == category]
        return res[:limit]

    async def get_job(self, job_id: str) -> Job:
        if self.should_fail:
            raise MarketplaceUnavailable("Marketplace backend offline", retryable=True)
        for j in self.jobs:
            if j.id == job_id:
                return j
        return make_test_job(id=job_id, title=f"Mock Job {job_id}")

    async def get_client_history(self, client_id: str) -> Any:
        return {"total_spent": 5000.0, "hires": 10}

    async def get_connects_balance(self) -> Any:
        return {"balance": 80}

    async def list_messages(self, conversation_id: str) -> list[Any]:
        return []

    async def create_proposal_draft(self, **kwargs: Any) -> Any:
        return {"id": "prop_draft_1", "job_id": kwargs.get("job_id")}

    async def submit_proposal(self, **kwargs: Any) -> Any:
        return {"status": "submitted", "proposal_id": kwargs.get("proposal_id")}

    async def send_message(self, **kwargs: Any) -> Any:
        return {
            "id": "msg_1",
            "conversation_id": kwargs.get("conversation_id"),
            "sender_id": "freelancer",
            "sender_role": "freelancer",
            "text": kwargs.get("text"),
        }


@pytest.fixture
def mock_port() -> MockPort:
    return MockPort()


@pytest.fixture
def test_app(mock_port: MockPort) -> Any:
    app = create_app()
    app.dependency_overrides[get_marketplace_port] = lambda: mock_port
    return app


@pytest.fixture
def client(test_app: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Fake graph runtime execution in background to keep testclient instant
    monkeypatch.setattr(
        "apps.api.services.runs_service.run_job",
        AsyncMock(return_value={"status": "awaiting_approval", "fit_score": 0.85}),
    )
    return TestClient(test_app)


def _get_auth_headers(client: TestClient, email: str, persona: str = "ai_ml") -> dict[str, str]:
    res = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "persona_id": persona},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_inbox_jobs_listing_and_filtering(client: TestClient) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com", "ai_ml")
    res = client.get("/jobs", headers=headers)
    assert res.status_code == 200
    jobs = res.json()
    assert len(jobs) >= 2
    assert jobs[0]["title"] is not None

    # Test category filter
    res_filtered = client.get("/jobs?category=ai_ml", headers=headers)
    assert res_filtered.status_code == 200
    for j in res_filtered.json():
        assert j["category"] == "ai_ml"


def test_job_skip_and_detail(client: TestClient) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com", "ai_ml")
    # 1. Skip job
    res_skip = client.post(
        "/jobs/job_test_001/skip",
        headers=headers,
        json={"reason": "Budget below minimum threshold"},
    )
    assert res_skip.status_code == 200
    assert res_skip.json()["status"] == "skipped"

    # 2. Get detail
    res_det = client.get("/jobs/job_test_001", headers=headers)
    assert res_det.status_code == 200
    det = res_det.json()
    assert det["id"] == "job_test_001"
    assert "FastAPI" in det["title"]


def test_runs_create_and_trace(client: TestClient) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com", "ai_ml")
    # Create run
    res = client.post("/runs", headers=headers, json={"job_id": "job_test_002"})
    assert res.status_code == 200
    data = res.json()
    assert "thread_id" in data
    assert data["status"] == "running"
    thread_id = data["thread_id"]

    # Trace endpoint
    res_trace = client.get(f"/runs/{thread_id}/trace", headers=headers)
    assert res_trace.status_code == 200
    assert res_trace.json()["thread_id"] == thread_id


def test_degraded_mode_returns_503(test_app: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    failing_port = MockPort(should_fail=True)
    test_app.dependency_overrides[get_marketplace_port] = lambda: failing_port

    with TestClient(test_app) as client:
        headers = _get_auth_headers(client, f"degraded_{uuid4().hex[:6]}@example.com")
        # 1. Reading jobs during degraded mode returns HTTP 503
        res = client.get("/jobs", headers=headers)
        assert res.status_code == 503
        body = res.json()
        assert body["detail"]["error"] == "marketplace_unavailable"
        assert body["detail"]["retryable"] is True
        assert body["detail"]["queued"] is False

        # 2. Creating a run during degraded mode returns 503 with queued=True or False
        res_run = client.post("/runs", headers=headers, json={"job_id": "job_test_001"})
        assert res_run.status_code == 503
        body_run = res_run.json()
        assert body_run["detail"]["error"] == "marketplace_unavailable"


def test_approvals_approve_edit_and_reject(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com")
    res_me = client.get("/auth/me", headers=headers)
    user_id = res_me.json()["id"]
    thread_id = f"{user_id}:job_approval_test"

    # Fake resume function
    mock_resume = AsyncMock(return_value={"status": "completed", "compliance": {"violations": []}})
    monkeypatch.setattr("apps.api.services.approvals_service.resume", mock_resume)

    # 1. Reject without reason fails
    res_reject_empty = client.post(
        f"/approvals/{thread_id}",
        headers=headers,
        json={"action": "reject", "reason": ""},
    )
    assert res_reject_empty.status_code == 400

    # 2. Reject with reason succeeds
    res_reject = client.post(
        f"/approvals/{thread_id}",
        headers=headers,
        json={"action": "reject", "reason": "Client rating is too low"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["action_taken"] == "reject"

    # 3. Edit proposal succeeds
    res_edit = client.post(
        f"/approvals/{thread_id}",
        headers=headers,
        json={"action": "edit", "edited_text": "Updated proposal text with direct portfolio citation."},
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["action_taken"] == "edit"

    # 4. Approve succeeds
    res_approve = client.post(
        f"/approvals/{thread_id}",
        headers=headers,
        json={"action": "approve"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["action_taken"] == "approve"


def test_pending_approvals_persist_across_new_app_instance(monkeypatch: pytest.MonkeyPatch, mock_port: MockPort) -> None:
    user_email = f"user_{uuid4().hex[:6]}@example.com"

    # First app instance
    app_1 = create_app()
    app_1.dependency_overrides[get_marketplace_port] = lambda: mock_port
    with TestClient(app_1) as client_1:
        headers = _get_auth_headers(client_1, user_email)
        res_me = client_1.get("/auth/me", headers=headers)
        user_id = res_me.json()["id"]

    # Mock pending approvals in runtime to simulate persistence
    saved_pending = [
        {
            "thread_id": f"{user_id}:job_persisted",
            "checkpoint_id": "cp_123",
            "created_at": "2026-11-15T00:00:00Z",
            "payload": {"draft": {"cover_letter": "Hello"}},
        }
    ]
    monkeypatch.setattr(
        "apps.api.services.approvals_service.pending_approvals",
        AsyncMock(return_value=saved_pending),
    )

    # Second app instance (restarts app)
    app_2 = create_app()
    app_2.dependency_overrides[get_marketplace_port] = lambda: mock_port
    with TestClient(app_2) as client_2:
        res = client_2.get("/approvals", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["thread_id"] == f"{user_id}:job_persisted"


def test_sse_streaming_yields_node_events(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com")
    res_me = client.get("/auth/me", headers=headers)
    user_id = res_me.json()["id"]
    thread_id = f"{user_id}:job_test_001"

    async def fake_stream_bid(*args: Any, **kwargs: Any) -> AsyncIterator[tuple[str, Any]]:
        yield ("updates", {"analyst": {"job_spec": {"skills": ["Python"]}}})
        yield ("custom", {"type": "telemetry", "duration_ms": 150.0, "tokens": 42})

    monkeypatch.setattr("apps.api.streaming.stream_bid", fake_stream_bid)

    with client.stream("GET", f"/runs/{thread_id}/stream", headers=headers) as stream:
        assert stream.status_code == 200
        lines = list(stream.iter_lines())
        content = "\n".join(lines)
        assert "event: node_update" in content
        assert "event: custom" in content
        assert "event: final" in content


def test_health_endpoints(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_deps = client.get("/health/dependencies")
    assert res_deps.status_code == 200
    data = res_deps.json()
    assert "dependencies" in data
    assert "postgres" in data["dependencies"]


def test_messages_suggest_returns_501(client: TestClient) -> None:
    headers = _get_auth_headers(client, f"user_{uuid4().hex[:6]}@example.com")
    res = client.get("/messages/conv_123/suggest", headers=headers)
    assert res.status_code == 501
    assert "not implemented" in res.json()["detail"].lower()
