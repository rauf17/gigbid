"""Portfolio MCP Server (FastMCP, Streamable HTTP and stdio transports).

Features:
- Read-only tools for portfolio evidence discovery, deep case studies, and skill inventory.
- Tool annotations: readOnlyHint=True, idempotentHint=True, destructiveHint=False, openWorldHint=False.
- Resource templates: portfolio://case/{id} and portfolio://proposal/{id}.
- Prompt templates: screening question answering and job experience summarization.
- Dual transport: Streamable HTTP on port 8001 (/mcp) and stdio mode (--stdio).
- Optional Bearer token authentication via PORTFOLIO_MCP_TOKEN (skipped in stdio mode).
- Dynamic persona selection via X-Persona HTTP header or PORTFOLIO_PERSONA env var.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_servers.portfolio.prompts import register_portfolio_prompts
from mcp_servers.portfolio.resources import register_portfolio_resources
from mcp_servers.portfolio.tools import register_portfolio_tools

DEFAULT_PORT = 8001
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PERSONA = "ai_ml"

current_persona: ContextVar[str] = ContextVar("current_persona", default=DEFAULT_PERSONA)


def get_current_persona() -> str:
    """Returns active persona from ContextVar or PORTFOLIO_PERSONA env var."""
    val = current_persona.get()
    if val:
        return val
    return os.getenv("PORTFOLIO_PERSONA", DEFAULT_PERSONA).strip()


def create_mcp_server(
    default_persona: str | None = None,
    data_dir: Path | str | None = None,
    use_hash_embedder: bool = False,
    vector_store: Any | None = None,
) -> FastMCP:
    """Builds and configures the FastMCP server with tools, resources, and prompts."""
    if default_persona:
        current_persona.set(default_persona)

    mcp = FastMCP("Portfolio MCP Server", streamable_http_path="/mcp")

    # 1. Register tools
    register_portfolio_tools(
        mcp=mcp,
        get_persona_fn=get_current_persona,
        data_dir=data_dir,
        use_hash_embedder=use_hash_embedder,
        vector_store=vector_store,
    )

    # 2. Register resource templates
    register_portfolio_resources(
        mcp=mcp,
        get_persona_fn=get_current_persona,
        data_dir=data_dir,
    )

    # 3. Register prompt templates
    register_portfolio_prompts(
        mcp=mcp,
        get_persona_fn=get_current_persona,
    )

    return mcp


class PortfolioAuthMiddleware(BaseHTTPMiddleware):
    """Enforces optional Bearer authentication and extracts X-Persona header context."""

    def __init__(self, app: Any, expected_token: str | None = None) -> None:
        super().__init__(app)
        self.expected_token = expected_token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Ignore CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Persona extraction from header
        persona_hdr = request.headers.get("X-Persona")
        if persona_hdr:
            current_persona.set(persona_hdr.strip())
        else:
            current_persona.set(os.getenv("PORTFOLIO_PERSONA", DEFAULT_PERSONA).strip())

        # Optional Bearer auth check
        token = self.expected_token or os.getenv("PORTFOLIO_MCP_TOKEN")
        if token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Missing Bearer token in Authorization header."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )

            incoming_token = auth_header.removeprefix("Bearer ").strip()
            if incoming_token != token:
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Invalid Bearer token."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return await call_next(request)


def create_app(
    mcp_instance: FastMCP | None = None,
    expected_token: str | None = None,
    data_dir: Path | str | None = None,
    use_hash_embedder: bool = False,
    vector_store: Any | None = None,
) -> Starlette:
    """Builds ASGI Starlette application with streamable HTTP transport and middleware."""
    server = mcp_instance or create_mcp_server(
        data_dir=data_dir,
        use_hash_embedder=use_hash_embedder,
        vector_store=vector_store,
    )
    app = server.streamable_http_app()
    app.add_middleware(
        PortfolioAuthMiddleware,
        expected_token=expected_token,
    )
    return app


# Default singleton for ASGI servers (uvicorn mcp_servers.portfolio.server:app --port 8001)
mcp_server = create_mcp_server()
app = create_app(mcp_instance=mcp_server)


def main() -> None:
    """CLI entrypoint for gigbid-portfolio-mcp console script."""
    parser = argparse.ArgumentParser(description="GigBid Portfolio MCP Server")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode for desktop clients")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port number (default: {DEFAULT_PORT})")
    parser.add_argument("--persona", default=None, help="Default freelancer persona (ai_ml, fullstack, data_analyst)")
    parser.add_argument("--hash-embedder", action="store_true", help="Use offline HashEmbedder for zero-download run")

    args = parser.parse_args()

    use_hash = args.hash_embedder or os.getenv("USE_HASH_EMBEDDER", "").lower() in {"1", "true", "yes"}

    if args.stdio:
        server = create_mcp_server(
            default_persona=args.persona,
            use_hash_embedder=use_hash,
        )
        asyncio.run(server.run_stdio_async())
    else:
        import uvicorn

        asgi_app = create_app(
            expected_token=os.getenv("PORTFOLIO_MCP_TOKEN"),
            use_hash_embedder=use_hash,
        )
        uvicorn.run(asgi_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
