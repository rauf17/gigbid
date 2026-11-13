"""Unit tests for Marketplace MCP Server using in-memory client and ASGI transport."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.marketplace.adapters.base import (
    MarketplaceAdapter,
    MarketplaceUnavailable,
    NotFound,
)
from mcp_servers.marketplace.audit import AuditStore
from mcp_servers.marketplace.ratelimit import MarketplaceRateLimiter
from mcp_servers.marketplace.server import create_app, create_mcp_server


class FakeMarketplaceAdapter(MarketplaceAdapter):
    """Deterministic in-memory adapter for unit testing tools."""

    def __init__(self) -> None:
        self.submit_count = 0
        self.connects_balance = 100
        self.proposals: dict[str, dict[str, Any]] = {}
        self.messages: list[dict[str, Any]] = []
        self.simulate_unavailable = False

    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        return [
            {
                "id": "job_unit_01",
                "title": "Build AI Agents with MCP",
                "description": "Looking for specialist to build FastMCP adapters.",
                "category": "AI/ML",
                "skills": ["Python", "MCP", "FastAPI"],
                "budget_type": "fixed",
                "budget_min": 2500.0,
                "budget_max": 3500.0,
                "client_country": "United States",
                "posted_at": "2026-11-13T12:00:00Z",
                "connects_cost": 8,
                "client_id": "client_01",
                "synthetic": True,
            }
        ]

    async def get_job(self, job_id: str) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        if job_id != "job_unit_01":
            raise NotFound(f"Job {job_id} not found.")
        return {
            "id": job_id,
            "title": "Build AI Agents with MCP",
            "description": "Looking for specialist to build FastMCP adapters.",
            "category": "AI/ML",
            "skills": ["Python", "MCP"],
            "budget_type": "fixed",
            "budget_min": 2500.0,
            "budget_max": 3500.0,
            "client_country": "United States",
            "posted_at": "2026-11-13T12:00:00Z",
            "connects_cost": 8,
            "client_id": "client_01",
            "synthetic": True,
        }

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        return {
            "id": client_id,
            "company": "Apex AI Labs",
            "industry": "Artificial Intelligence",
            "country": "United States",
            "payment_verified": True,
            "total_spent": 125000.0,
            "hire_rate": 0.85,
            "avg_rating": 4.95,
            "jobs_posted": 42,
            "review_count": 38,
        }

    async def get_connects_balance(self) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        return {"connects_balance": self.connects_balance, "currency": "Connects"}

    async def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        return [
            m for m in self.messages if m.get("conversation_id") == conversation_id
        ]

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        prop_id = f"prop_draft_{uuid4().hex[:8]}"
        data = {
            "id": prop_id,
            "job_id": job_id,
            "cover_letter": cover_letter,
            "screening_answers": screening_answers,
            "bid_amount": bid_amount,
            "connects_cost": 8,
            "status": "draft",
            "created_at": "2026-11-13T12:00:00Z",
            "dry_run": dry_run,
            "message": "Draft created successfully.",
        }
        if not dry_run:
            self.proposals[prop_id] = data
        return data

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        if proposal_id not in self.proposals and not dry_run:
            raise NotFound(f"Proposal {proposal_id} not found.")

        cost = 8
        if dry_run:
            return {
                "id": proposal_id,
                "job_id": "job_unit_01",
                "status": "draft",
                "connects_cost": cost,
                "connects_balance": self.connects_balance,
                "submitted_at": None,
                "dry_run": True,
                "message": "Dry run preview: proposal ready to submit.",
            }

        self.submit_count += 1
        self.connects_balance -= cost
        prop = self.proposals[proposal_id]
        prop["status"] = "submitted"
        return {
            "id": proposal_id,
            "job_id": prop["job_id"],
            "status": "submitted",
            "connects_cost": cost,
            "connects_balance": self.connects_balance,
            "submitted_at": "2026-11-13T12:01:00Z",
            "dry_run": False,
            "message": "Proposal submitted and Connects charged.",
        }

    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if self.simulate_unavailable:
            raise MarketplaceUnavailable("Marketplace backend is down.")
        msg = {
            "id": f"msg_{uuid4().hex[:8]}",
            "conversation_id": conversation_id,
            "sender": "freelancer",
            "text": text,
            "created_at": "2026-11-13T12:02:00Z",
            "dry_run": dry_run,
        }
        if not dry_run:
            self.messages.append(msg)
        return msg


@pytest.fixture
def test_setup(tmp_path: Any) -> tuple[Any, FakeMarketplaceAdapter, AuditStore, MarketplaceRateLimiter]:
    db_file = tmp_path / "test_audit.db"
    adapter = FakeMarketplaceAdapter()
    audit_store = AuditStore(db_path=db_file)
    rate_limiter = MarketplaceRateLimiter(max_requests=5, window_seconds=60.0)
    mcp, _, _, _ = create_mcp_server(
        adapter=adapter,
        audit_store=audit_store,
        rate_limiter=rate_limiter,
    )
    return mcp, adapter, audit_store, rate_limiter


@pytest.mark.asyncio
async def test_schema_constraint_rejections(test_setup: Any) -> None:
    """Verifies that Pydantic input model constraints reject invalid inputs."""
    mcp, _, _, _ = test_setup

    async with create_connected_server_and_client_session(mcp) as session:
        # 1. limit > 50 rejected
        res_limit = await session.call_tool("search_jobs", {"limit": 100})
        assert res_limit.isError
        assert "less than or equal to 50" in res_limit.content[0].text

        # 2. job_id too short (< 3 chars) rejected
        res_job = await session.call_tool("get_job", {"job_id": "ab"})
        assert res_job.isError
        assert "at least 3 characters" in res_job.content[0].text

        # 3. bid_amount <= 0 rejected
        res_bid = await session.call_tool(
            "create_proposal_draft",
            {
                "job_id": "job_unit_01",
                "cover_letter": "Short but valid length cover letter.",
                "bid_amount": -10.0,
                "idempotency_key": "valid-idemp-key-12345",
            },
        )
        assert res_bid.isError
        assert "greater than 0" in res_bid.content[0].text

        # 4. idempotency_key too short (< 8 chars) rejected
        res_idemp = await session.call_tool(
            "submit_proposal",
            {"proposal_id": "prop_01", "idempotency_key": "short"},
        )
        assert res_idemp.isError
        assert "at least 8 characters" in res_idemp.content[0].text


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(test_setup: Any) -> None:
    """Verifies dry_run=True returns preview with Connects cost without modifying state."""
    mcp, adapter, _, _ = test_setup

    async with create_connected_server_and_client_session(mcp) as session:
        # Draft dry-run
        res_draft = await session.call_tool(
            "create_proposal_draft",
            {
                "job_id": "job_unit_01",
                "cover_letter": "Here is an evidence-based high-quality proposal.",
                "bid_amount": 1500.0,
                "idempotency_key": "idemp-draft-dryrun-01",
                "dry_run": True,
            },
        )
        assert not res_draft.isError
        assert len(adapter.proposals) == 0

        # Submit dry-run
        res_submit = await session.call_tool(
            "submit_proposal",
            {
                "proposal_id": "prop_preview_01",
                "idempotency_key": "idemp-submit-dryrun-01",
                "dry_run": True,
            },
        )
        assert not res_submit.isError
        assert adapter.submit_count == 0
        assert adapter.connects_balance == 100

        # Message dry-run
        res_msg = await session.call_tool(
            "send_message",
            {
                "conversation_id": "conv_01",
                "text": "Hello client, checking on project requirements.",
                "idempotency_key": "idemp-msg-dryrun-01",
                "dry_run": True,
            },
        )
        assert not res_msg.isError
        assert len(adapter.messages) == 0


@pytest.mark.asyncio
async def test_retry_with_same_key_charges_connects_once(test_setup: Any) -> None:
    """Idempotent retry with same key returns cached result and avoids duplicate charge."""
    mcp, adapter, _, _ = test_setup

    async with create_connected_server_and_client_session(mcp) as session:
        # Create draft first
        draft_res = await session.call_tool(
            "create_proposal_draft",
            {
                "job_id": "job_unit_01",
                "cover_letter": "Valid proposal cover letter for testing idempotency.",
                "bid_amount": 2500.0,
                "idempotency_key": "idemp-draft-repeat-01",
                "dry_run": False,
            },
        )
        assert not draft_res.isError
        prop_id = next(iter(adapter.proposals.keys()))

        # Submit first time
        key = "idemp-submit-repeat-99"
        sub1 = await session.call_tool(
            "submit_proposal",
            {"proposal_id": prop_id, "idempotency_key": key, "dry_run": False},
        )
        assert not sub1.isError
        assert adapter.submit_count == 1
        assert adapter.connects_balance == 92

        # Submit second time with identical idempotency key
        sub2 = await session.call_tool(
            "submit_proposal",
            {"proposal_id": prop_id, "idempotency_key": key, "dry_run": False},
        )
        assert not sub2.isError
        # Submissions count and balance remain unchanged
        assert adapter.submit_count == 1
        assert adapter.connects_balance == 92


@pytest.mark.asyncio
async def test_audit_log_appends_and_masks_pii(test_setup: Any) -> None:
    """Verifies append-only audit log records invocations and redacts PII."""
    mcp, _, audit_store, _ = test_setup

    pii_cover_letter = (
        "Please email me at sensitive.freelancer@domain.com or call +1-555-888-9999. "
        "Deposit payment to credit card 4111 2222 3333 4444 or crypto 0x71C7656EC7ab88b098defB751B7401B5f6d8976F."
    )

    async with create_connected_server_and_client_session(mcp) as session:
        res = await session.call_tool(
            "create_proposal_draft",
            {
                "job_id": "job_unit_01",
                "cover_letter": pii_cover_letter,
                "bid_amount": 3000.0,
                "idempotency_key": "idemp-pii-mask-audit-01",
                "dry_run": False,
            },
        )
        assert not res.isError

    logs = audit_store.get_recent_logs(limit=10)
    assert len(logs) >= 1
    target_log = next((l for l in logs if l["tool"] == "create_proposal_draft"), None)
    assert target_log is not None
    assert target_log["status"] == "success"

    args_logged = target_log["arguments_json"]
    # Verify raw PII strings are ABSENT
    assert "sensitive.freelancer@domain.com" not in args_logged
    assert "+1-555-888-9999" not in args_logged
    assert "4111 2222 3333 4444" not in args_logged
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" not in args_logged

    # Verify redaction tokens are PRESENT
    assert "[EMAIL_MASKED]" in args_logged
    assert "[PHONE_MASKED]" in args_logged
    assert "[PAYMENT_MASKED]" in args_logged


@pytest.mark.asyncio
async def test_unavailable_adapter_produces_structured_error(test_setup: Any) -> None:
    """Degraded mode returns structured error response without crashing."""
    mcp, adapter, audit_store, _ = test_setup
    adapter.simulate_unavailable = True

    async with create_connected_server_and_client_session(mcp) as session:
        res = await session.call_tool("get_job", {"job_id": "job_unit_01"})
        assert not res.isError
        text = res.content[0].text
        assert "marketplace_unavailable" in text
        assert '"retryable": true' in text

    logs = audit_store.get_recent_logs(limit=5)
    assert logs[0]["status"] == "degraded"


@pytest.mark.asyncio
async def test_http_auth_401(tmp_path: Any) -> None:
    """Verifies HTTP transport rejects missing or invalid Bearer tokens with 401."""
    db_file = tmp_path / "test_auth_audit.db"
    adapter = FakeMarketplaceAdapter()
    audit_store = AuditStore(db_path=db_file)
    rate_limiter = MarketplaceRateLimiter(max_requests=10, window_seconds=60.0)

    app = create_app(
        adapter=adapter,
        audit_store=audit_store,
        rate_limiter=rate_limiter,
        token="super-secret-mcp-token-123",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. No Authorization header -> 401
        r1 = await client.post("/mcp")
        assert r1.status_code == 401
        assert "Bearer" in r1.headers.get("WWW-Authenticate", "")

        # 2. Bad token -> 401
        r2 = await client.post("/mcp", headers={"Authorization": "Bearer wrong-token"})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_rate_limiter_trips(tmp_path: Any) -> None:
    """Verifies per-user sliding window rate limiter triggers 429 when threshold exceeded."""
    db_file = tmp_path / "test_rl_audit.db"
    adapter = FakeMarketplaceAdapter()
    audit_store = AuditStore(db_path=db_file)
    rate_limiter = MarketplaceRateLimiter(max_requests=3, window_seconds=60.0)
    token = "test-token-rl"

    app = create_app(
        adapter=adapter,
        audit_store=audit_store,
        rate_limiter=rate_limiter,
        token=token,
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Id": "limited-freelancer-user",
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # First 3 requests pass auth and rate limiting
            for _ in range(3):
                resp = await client.post("/mcp", headers=headers)
                # Response may be 400/404/200 depending on body, but NOT 429
                assert resp.status_code != 429

            # 4th request trips rate limit -> 429
            resp4 = await client.post("/mcp", headers=headers)
            assert resp4.status_code == 429
            assert "Retry-After" in resp4.headers
            data = resp4.json()
            assert data.get("error") == "rate_limited"
