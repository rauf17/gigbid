"""Comprehensive tests for Portfolio MCP Server using in-memory MCP session and HTTP transport."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.portfolio.server import create_app, create_mcp_server


@pytest.fixture
def mcp_test_server() -> Any:
    """Builds FastMCP server instance configured with HashEmbedder for offline tests."""
    return create_mcp_server(
        default_persona="ai_ml",
        use_hash_embedder=True,
    )


@pytest.mark.asyncio
async def test_tool_annotations_and_schema(mcp_test_server: Any) -> None:
    """Verifies that all tools carry strict readOnly, idempotent, non-destructive hints."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        tools_res = await session.list_tools()
        tools = tools_res.tools
        tool_names = {t.name for t in tools}
        assert "search_evidence" in tool_names
        assert "get_case_study" in tool_names
        assert "list_skills" in tool_names

        for tool in tools:
            ann = tool.annotations
            assert ann is not None, f"Tool {tool.name} must have annotations"
            assert ann.readOnlyHint is True, f"{tool.name} readOnlyHint must be True"
            assert ann.idempotentHint is True, f"{tool.name} idempotentHint must be True"
            assert ann.destructiveHint is False, f"{tool.name} destructiveHint must be False"
            assert ann.openWorldHint is False, f"{tool.name} openWorldHint must be False"


@pytest.mark.asyncio
async def test_search_evidence_valid_and_filters(mcp_test_server: Any) -> None:
    """Tests search_evidence with valid input and optional metadata filters."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        res = await session.call_tool(
            "search_evidence",
            {"requirement": "machine learning pipeline", "k": 3},
        )
        assert not res.isError
        data = json.loads(res.content[0].text)
        assert data["persona"] == "ai_ml"
        assert "items" in data

        # With filter
        filtered_res = await session.call_tool(
            "search_evidence",
            {
                "requirement": "data modeling",
                "k": 2,
                "filters": {"type": "case_study"},
            },
        )
        assert not filtered_res.isError
        filtered_data = json.loads(filtered_res.content[0].text)
        for item in filtered_data.get("items", []):
            assert item["type"] == "case_study"


@pytest.mark.asyncio
async def test_search_evidence_input_validation(mcp_test_server: Any) -> None:
    """Tests input constraints on search_evidence (length 3..500, k 1..20)."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        # Too short (< 3 chars)
        res_short = await session.call_tool("search_evidence", {"requirement": "ab"})
        assert res_short.isError or "invalid_argument" in res_short.content[0].text

        # k out of range (> 20)
        res_k = await session.call_tool("search_evidence", {"requirement": "valid query", "k": 50})
        assert res_k.isError or "invalid_argument" in res_k.content[0].text

        # Invalid filter type
        res_type = await session.call_tool(
            "search_evidence",
            {"requirement": "valid query", "filters": {"type": "invalid_type_name"}},
        )
        assert res_type.isError or "invalid_argument" in res_type.content[0].text


@pytest.mark.asyncio
async def test_get_case_study(mcp_test_server: Any) -> None:
    """Tests get_case_study retrieves valid case study and handles missing IDs gracefully."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        # Valid ID
        res = await session.call_tool("get_case_study", {"id": "cs_01"})
        assert not res.isError
        data = json.loads(res.content[0].text)
        assert "project" in data
        assert "text" in data
        assert len(data["text"]) > 20

        # Missing ID returns clean error, never crashes
        res_missing = await session.call_tool("get_case_study", {"id": "non_existent_project_999"})
        assert not res_missing.isError
        missing_data = json.loads(res_missing.content[0].text)
        assert missing_data.get("error") == "not_found"


@pytest.mark.asyncio
async def test_list_skills(mcp_test_server: Any) -> None:
    """Tests list_skills returns deduplicated skills with count backing."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        res = await session.call_tool("list_skills", {})
        assert not res.isError
        data = json.loads(res.content[0].text)
        assert data["persona"] == "ai_ml"
        assert data["total_skills"] > 0
        assert len(data["skills"]) > 0

        first_skill = data["skills"][0]
        assert "skill" in first_skill
        assert first_skill["count"] >= 1


@pytest.mark.asyncio
async def test_resource_templates(mcp_test_server: Any) -> None:
    """Tests portfolio://case/{id} and portfolio://proposal/{id} resource templates."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        # Case study resource
        case_content = await session.read_resource("portfolio://case/cs_01")
        assert len(case_content.contents) > 0
        assert len(case_content.contents[0].text) > 20

        # Proposal resource
        proposal_content = await session.read_resource("portfolio://proposal/prop_0001")
        assert len(proposal_content.contents) > 0
        assert "Proposal" in proposal_content.contents[0].text

        # Non-existent resource raises or fails cleanly
        with pytest.raises(Exception):  # noqa: B017
            await session.read_resource("portfolio://case/non_existent_id")


@pytest.mark.asyncio
async def test_prompt_templates(mcp_test_server: Any) -> None:
    """Tests MCP prompt templates rendering instructions to cite evidence IDs."""
    async with create_connected_server_and_client_session(mcp_test_server) as session:
        # 1. Screening question prompt
        prompt1 = await session.get_prompt(
            "Answer a screening question from my portfolio",
            {"question": "How do you mitigate data distribution drift?"},
        )
        assert len(prompt1.messages) > 0
        text1 = prompt1.messages[0].content.text
        assert "mitigate data distribution drift" in text1
        assert "search_evidence" in text1
        assert "NEVER invent" in text1

        # 2. Job summarization prompt
        prompt2 = await session.get_prompt(
            "Summarise my most relevant experience for this job",
            {"job_text": "Need senior ML engineer to build low-latency RAG pipeline."},
        )
        assert len(prompt2.messages) > 0
        text2 = prompt2.messages[0].content.text
        assert "low-latency RAG pipeline" in text2
        assert "search_evidence" in text2


@pytest.mark.asyncio
async def test_http_auth_and_persona_header(tmp_path: Path) -> None:
    """Tests ASGI HTTP server auth enforcement and X-Persona dynamic routing."""
    token = "secret-portfolio-token-xyz"
    app = create_app(
        expected_token=token,
        use_hash_embedder=True,
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Missing Bearer auth -> 401
            r_unauth = await client.post("/mcp")
            assert r_unauth.status_code == 401

            # 2. Invalid Bearer token -> 401
            r_bad = await client.post("/mcp", headers={"Authorization": "Bearer wrong-token"})
            assert r_bad.status_code == 401

            # 3. Valid Bearer token + X-Persona header passes auth
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Persona": "fullstack",
            }
            r_ok = await client.post("/mcp", headers=headers)
            # Auth passed: status code is not 401
            assert r_ok.status_code != 401
