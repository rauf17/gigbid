"""In-memory tests for Workspace MCP server, schemas, idempotency, and auth."""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from mcp_servers.workspace.schemas import ListFreeSlotsInput
from mcp_servers.workspace.server import create_app, create_mcp_server
from mcp_servers.workspace.store import WorkspaceStore


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceStore(state_dir=Path(tmpdir))


@pytest.mark.asyncio
async def test_list_free_slots_in_memory(temp_store: WorkspaceStore):
    slots = temp_store.list_free_slots(days_ahead=3, duration_min=30)
    assert len(slots) > 0
    first = slots[0]
    assert first.slot_id.startswith("slot_")
    assert first.duration_min == 30
    assert "UTC" in first.formatted


@pytest.mark.asyncio
async def test_tentative_hold_idempotency(temp_store: WorkspaceStore):
    slots = temp_store.list_free_slots(days_ahead=2, duration_min=30)
    assert len(slots) > 0
    target_slot = slots[0].slot_id

    # 1. Create tentative hold
    hold1 = temp_store.create_tentative_hold(
        slot_id=target_slot,
        title="Intro Interview with Client Acme",
        idempotency_key="idem_key_hold_123",
    )
    assert hold1.status == "tentative"
    assert hold1.slot_id == target_slot

    # 2. Call again with same idempotency key
    hold2 = temp_store.create_tentative_hold(
        slot_id=target_slot,
        title="Intro Interview with Client Acme",
        idempotency_key="idem_key_hold_123",
    )
    assert hold2.hold_id == hold1.hold_id
    assert hold2.held_at == hold1.held_at

    # 3. Target slot is now excluded from free slots
    remaining = temp_store.list_free_slots(days_ahead=2, duration_min=30)
    assert target_slot not in [s.slot_id for s in remaining]


@pytest.mark.asyncio
async def test_email_draft_idempotency(temp_store: WorkspaceStore):
    draft1 = temp_store.create_email_draft(
        to="client@example.com",
        subject="Project Follow-Up",
        body="Thank you for considering our proposal.",
        idempotency_key="idem_key_draft_456",
    )
    assert draft1.status == "draft"
    assert draft1.to == "client@example.com"

    # Call again with same idempotency key
    draft2 = temp_store.create_email_draft(
        to="client@example.com",
        subject="Project Follow-Up",
        body="Thank you for considering our proposal.",
        idempotency_key="idem_key_draft_456",
    )
    assert draft2.draft_id == draft1.draft_id
    assert draft2.created_at == draft1.created_at


@pytest.mark.asyncio
async def test_fastmcp_tools_registration(temp_store: WorkspaceStore):
    mcp, _ = create_mcp_server(store=temp_store)
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "list_free_slots" in tool_names
    assert "create_tentative_hold" in tool_names
    assert "create_email_draft" in tool_names


@pytest.mark.asyncio
async def test_workspace_http_auth_and_calls(temp_store: WorkspaceStore):
    secret = "test-token-secret-789"
    app = create_app(store=temp_store, token=secret)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # 1. Missing auth -> 401
        res_unauth = await client.post("/mcp", json={})
        assert res_unauth.status_code == 401

        # 2. Invalid auth -> 401
        res_bad = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer wrong-token"},
            json={},
        )
        assert res_bad.status_code == 401


def test_schema_constraints():
    # Valid input
    valid = ListFreeSlotsInput(days_ahead=5, duration_min=45)
    assert valid.days_ahead == 5

    # Invalid input (days_ahead > 14)
    with pytest.raises(ValidationError):
        ListFreeSlotsInput(days_ahead=20, duration_min=45)

    # Invalid duration (< 15)
    with pytest.raises(ValidationError):
        ListFreeSlotsInput(days_ahead=3, duration_min=5)
