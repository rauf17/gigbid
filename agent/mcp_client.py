"""MCP client builder and per-agent tool allowlist configuration.

Requirements R1 / A2:
- Restricts tool capabilities based on agent role.
- Read tools: scout, risk_assessor, pricing.
- Messaging: client_liaison.
- Destructive proposal submissions / drafts: approval/submit only.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from langchain_mcp_adapters.client import MultiServerMCPClient

TOOL_ALLOWLIST: dict[str, set[str]] = {
    "scout": {
        "search_jobs",
        "get_job",
    },
    "risk_assessor": {
        "get_job",
        "get_client_history",
    },
    "pricing": {
        "get_job",
        "get_client_history",
        "get_connects_balance",
    },
    "client_liaison": {
        "get_job",
        "get_client_history",
        "list_messages",
        "send_message",
    },
    "approval": {
        "get_job",
        "get_client_history",
        "get_connects_balance",
        "create_proposal_draft",
        "submit_proposal",
    },
    "submit": {
        "get_job",
        "get_client_history",
        "get_connects_balance",
        "create_proposal_draft",
        "submit_proposal",
    },
}


def build_client(
    server_names: list[str] | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
) -> MultiServerMCPClient:
    """Builds a MultiServerMCPClient configured with Streamable HTTP connections."""
    targets = server_names or ["marketplace"]
    effective_trace = trace_id or uuid4().hex
    effective_user = user_id or "freelancer-user-1"

    connections: dict[str, Any] = {}

    if "marketplace" in targets:
        mkt_url = os.getenv("MARKETPLACE_MCP_URL", "http://127.0.0.1:8002/mcp")
        if not mkt_url.endswith("/mcp"):
            mkt_url = f"{mkt_url.rstrip('/')}/mcp"
        mkt_token = os.getenv("MARKETPLACE_MCP_TOKEN", "marketplace-dev-token-secret-123")

        connections["marketplace"] = {
            "transport": "streamable_http",
            "url": mkt_url,
            "headers": {
                "Authorization": f"Bearer {mkt_token}",
                "X-Trace-Id": effective_trace,
                "X-User-Id": effective_user,
            },
        }

    if "portfolio" in targets:
        port_url = os.getenv("PORTFOLIO_MCP_URL", "http://127.0.0.1:8003/mcp")
        connections["portfolio"] = {
            "transport": "streamable_http",
            "url": port_url,
            "headers": {"X-Trace-Id": effective_trace},
        }

    if "workspace" in targets:
        work_url = os.getenv("WORKSPACE_MCP_URL", "http://127.0.0.1:8004/mcp")
        connections["workspace"] = {
            "transport": "streamable_http",
            "url": work_url,
            "headers": {"X-Trace-Id": effective_trace},
        }

    return MultiServerMCPClient(connections=connections)


def filter_tools_for_agent(agent_name: str, tools: list[Any]) -> list[Any]:
    """Filters a list of tools according to the agent's permission allowlist."""
    allowed = TOOL_ALLOWLIST.get(agent_name, set())
    return [t for t in tools if getattr(t, "name", str(t)) in allowed]
