"""In-process integration test connecting MarketplacePort, MCP server, and GigSim.

Executes the full required flow:
search -> get_job -> draft(dry_run) -> draft -> submit(dry_run) -> submit -> same-key submit.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from agent.marketplace_port import McpMarketplacePort
from gigsim.app import app as gigsim_app
from gigsim.seed import get_db_connection, reset_database, seed_database
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.audit import AuditStore
from mcp_servers.marketplace.server import create_mcp_server

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
CLIENTS_FILE = Path(__file__).resolve().parent.parent.parent / "gigsim" / "seed" / "clients.json"


@pytest.fixture
def seeded_gigsim(tmp_path: Any) -> Any:
    """Initializes in-process GigSim simulator with fresh state."""
    os.environ["GIGSIM_TESTING"] = "1"
    os.environ["GIGSIM_FAULT_RATE"] = "0.0"
    os.environ.pop("GIGSIM_TEST_RATE_LIMIT", None)
    token = "integration-gigsim-token-456"
    os.environ["GIGSIM_API_TOKEN"] = token

    conn = get_db_connection()
    reset_database(conn)
    seed_database(
        conn=conn,
        stream_jobs_file=DATA_DIR / "jobs_stream.jsonl",
        clients_file=CLIENTS_FILE,
        initial_release_count=10,
    )
    yield token
    os.environ.pop("GIGSIM_API_TOKEN", None)
    os.environ["GIGSIM_TESTING"] = "1"


@pytest.mark.asyncio
async def test_marketplace_port_gigsim_flow(seeded_gigsim: str, tmp_path: Any) -> None:
    """Tests the full end-to-end freelancer journey through the MarketplacePort."""
    token = seeded_gigsim
    audit_file = tmp_path / "integration_audit.db"
    audit_store = AuditStore(db_path=audit_file)

    # 1. Connect GigSimAdapter to in-process GigSim app via ASGITransport
    transport = httpx.ASGITransport(app=gigsim_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as http_client:
        adapter = GigSimAdapter(client=http_client)

        # 2. Build MCP server hosting tools with this adapter
        mcp, _, _, _ = create_mcp_server(adapter=adapter, audit_store=audit_store)

        # 3. Connect McpMarketplacePort through SDK in-memory session
        async with create_connected_server_and_client_session(mcp) as session:
            port = McpMarketplacePort(in_memory_session=session)

            # Step A: search_jobs
            jobs = await port.search_jobs(limit=10)
            assert len(jobs) > 0, "Expected released jobs from GigSim."
            target_job = jobs[0]
            assert target_job.id
            assert target_job.connects_cost > 0

            # Step B: get_job
            job_details = await port.get_job(target_job.id)
            assert job_details.id == target_job.id
            assert job_details.title == target_job.title

            # Step C: Check initial Connects balance
            bal_start = await port.get_connects_balance()
            assert bal_start.balance >= target_job.connects_cost

            # Step D: create_proposal_draft with dry_run=True (Preview)
            cover_letter = (
                "Here is my technical proposal. I previously shipped an enterprise RAG search system "
                "with sub-second retrieval latency on 4.5M pages and 91% factual accuracy."
            )
            dry_draft = await port.create_proposal_draft(
                job_id=target_job.id,
                cover_letter=cover_letter,
                bid_amount=target_job.budget_max or 2500.0,
                idempotency_key="integ-draft-dryrun-01",
                dry_run=True,
            )
            assert dry_draft.dry_run is True
            assert dry_draft.connects_cost == target_job.connects_cost

            # Step E: create_proposal_draft with dry_run=False (Persisted)
            real_draft = await port.create_proposal_draft(
                job_id=target_job.id,
                cover_letter=cover_letter,
                bid_amount=target_job.budget_max or 2500.0,
                idempotency_key="integ-draft-real-01",
                dry_run=False,
            )
            assert real_draft.status == "draft"
            assert real_draft.dry_run is False
            prop_id = real_draft.id

            # Balance should still be untouched after creating draft
            bal_after_draft = await port.get_connects_balance()
            assert bal_after_draft.balance == bal_start.balance

            # Step F: submit_proposal with dry_run=True (Preview)
            dry_sub = await port.submit_proposal(
                proposal_id=prop_id,
                idempotency_key="integ-submit-key-01",
                dry_run=True,
            )
            assert dry_sub.dry_run is True
            assert dry_sub.connects_cost == target_job.connects_cost

            bal_after_dry_sub = await port.get_connects_balance()
            assert bal_after_dry_sub.balance == bal_start.balance

            # Step G: submit_proposal with dry_run=False (Spends Connects)
            real_sub = await port.submit_proposal(
                proposal_id=prop_id,
                idempotency_key="integ-submit-key-01",
                dry_run=False,
            )
            assert real_sub.status == "submitted"
            assert real_sub.connects_cost == target_job.connects_cost
            expected_balance = bal_start.balance - target_job.connects_cost
            assert real_sub.connects_balance == expected_balance

            bal_final = await port.get_connects_balance()
            assert bal_final.balance == expected_balance

            # Step H: submit_proposal again with SAME idempotency key (Idempotent replay)
            replay_sub = await port.submit_proposal(
                proposal_id=prop_id,
                idempotency_key="integ-submit-key-01",
                dry_run=False,
            )
            assert replay_sub.id == real_sub.id
            # Balance must NOT be deducted again
            bal_replay = await port.get_connects_balance()
            assert bal_replay.balance == expected_balance

    # Verify audit store logged the sequence
    logs = audit_store.get_recent_logs(limit=20)
    tool_names = [l["tool"] for l in logs]
    assert "search_jobs" in tool_names
    assert "get_job" in tool_names
    assert "create_proposal_draft" in tool_names
    assert "submit_proposal" in tool_names
