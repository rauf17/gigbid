"""Unit tests for background worker tasks and idempotency guarantees."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from agent.marketplace_models import Job
from agent.marketplace_port import MarketplacePort
from worker.tasks import analyse_job, check_budget_and_limits, scout_saved_search


def make_worker_test_job(job_id: str, title: str, category: str = "ai_ml") -> Job:
    return Job(
        id=job_id,
        title=title,
        description="Worker task candidate job description",
        category=category,
        skills=["Python"],
        budget_type="fixed",
        budget_min=100.0,
        budget_max=500.0,
        client_country="US",
        posted_at="2026-11-15T00:00:00Z",
        connects_cost=4,
    )


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.enqueued: list[dict[str, Any]] = []

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.enqueued.append({"name": name, "args": args, "kwargs": kwargs})


class FakeWorkerPort(MarketplacePort):
    def __init__(self) -> None:
        self.jobs = [
            make_worker_test_job("job_scout_1", "Python Scraper", "ai_ml"),
            make_worker_test_job("job_scout_2", "FastAPI Microservice", "fullstack"),
        ]

    async def search_jobs(self, **kwargs: Any) -> list[Job]:
        return self.jobs

    async def get_job(self, job_id: str) -> Job:
        return make_worker_test_job(job_id, f"Job {job_id}", "ai_ml")

    async def get_client_history(self, client_id: str) -> Any:
        return {}

    async def get_connects_balance(self) -> Any:
        return {"balance": 100}

    async def list_messages(self, conversation_id: str) -> list[Any]:
        return []

    async def create_proposal_draft(self, **kwargs: Any) -> Any:
        return {"id": "p1"}

    async def submit_proposal(self, **kwargs: Any) -> Any:
        return {"status": "submitted"}

    async def send_message(self, **kwargs: Any) -> Any:
        return {}


@pytest.mark.asyncio
async def test_scout_saved_search_enqueues_jobs() -> None:
    fake_redis = FakeRedis()
    fake_port = FakeWorkerPort()
    ctx = {"redis": fake_redis, "port": fake_port}

    user_id = f"worker_usr_{uuid4().hex[:6]}"
    res = await scout_saved_search(ctx, user_id=user_id, search_id="default")
    assert res["status"] == "ok"
    assert res["enqueued"] == 2
    assert len(fake_redis.enqueued) == 2

    # Second scout call should deduplicate via Redis and enqueue 0 new jobs
    res_second = await scout_saved_search(ctx, user_id=user_id, search_id="default")
    assert res_second["status"] == "ok"
    assert res_second["enqueued"] == 0
    assert len(fake_redis.enqueued) == 2  # unchanged!


@pytest.mark.asyncio
async def test_analyse_job_idempotency_prevents_duplicate_runs() -> None:
    fake_redis = FakeRedis()
    fake_port = FakeWorkerPort()
    ctx = {"redis": fake_redis, "port": fake_port}

    user_id = f"worker_usr_{uuid4().hex[:6]}"
    job_id = "job_test_idem_101"

    # Pre-mark job as analysed in Redis to simulate worker restart / duplicate delivery
    await fake_redis.set(f"job_analysed:{user_id}:{job_id}", "1")

    res = await analyse_job(ctx, user_id=user_id, job_id=job_id)
    assert res["status"] == "already_analysed"
    assert res["job_id"] == job_id


def test_budget_check_allows_under_budget() -> None:
    user_id = f"budget_usr_{uuid4().hex[:6]}"
    assert check_budget_and_limits(user_id) is True
