"""Contract snapshot test for Workspace MCP server tool signatures.

Fails when a tool name, input schema, output schema, or annotation changes unintentionally.

To deliberately update the contract snapshot after intended schema changes, run:
    uv run pytest tests/contract/test_workspace_schema_snapshot.py --update-snapshot
or:
    UPDATE_SNAPSHOT=1 uv run pytest tests/contract/test_workspace_schema_snapshot.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from mcp_servers.workspace.server import create_mcp_server

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
SNAPSHOT_PATH = SNAPSHOT_DIR / "workspace_tools.json"


def _normalize_tool(tool: Any) -> dict[str, Any]:
    dump = tool.model_dump()
    return {
        "name": dump.get("name"),
        "description": dump.get("description"),
        "inputSchema": dump.get("inputSchema"),
        "outputSchema": dump.get("outputSchema"),
        "annotations": dump.get("annotations"),
    }


@pytest.mark.asyncio
async def test_workspace_tools_schema_snapshot(pytestconfig: pytest.Config) -> None:
    """Verifies the registered workspace tools match the frozen contract snapshot."""
    mcp, _ = create_mcp_server()
    tools = await mcp.list_tools()

    sorted_tools = sorted(tools, key=lambda t: t.name)
    current_schema = [_normalize_tool(t) for t in sorted_tools]
    current_json = json.dumps(current_schema, indent=2, sort_keys=True)

    should_update = (
        pytestconfig.getoption("--update-snapshot", default=False)
        or os.getenv("UPDATE_SNAPSHOT", "").lower() in {"1", "true", "yes"}
        or not SNAPSHOT_PATH.exists()
    )

    if should_update:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(current_json + "\n", encoding="utf-8")
        if not SNAPSHOT_PATH.exists():
            pytest.skip(f"Created contract snapshot at {SNAPSHOT_PATH}")

    expected_json = SNAPSHOT_PATH.read_text(encoding="utf-8").strip()
    assert current_json == expected_json, (
        "Workspace tool contract schema has changed! If this was intentional, update "
        "the snapshot via: UPDATE_SNAPSHOT=1 uv run pytest tests/contract/test_workspace_schema_snapshot.py"
    )
