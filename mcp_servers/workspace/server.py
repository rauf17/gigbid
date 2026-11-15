"""Workspace MCP Server (FastMCP, Streamable HTTP transport and stdio).

Provides tools for calendar availability lookup, tentative interview holds, and email drafts.
Runs over a local deterministic mock store (JSON file under mcp_servers/workspace/state/).

NOTE: Real Google Calendar and Gmail APIs are NOT wired (mock only for assignment requirements).
"""
from __future__ import annotations

import argparse
import os
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_servers.workspace.schemas import (
    EmailDraftOutput,
    ListFreeSlotsOutput,
    TentativeHoldOutput,
)
from mcp_servers.workspace.store import WorkspaceStore

DEFAULT_PORT = 8003
DEFAULT_TOKEN = os.getenv("WORKSPACE_MCP_TOKEN", "workspace-dev-token-secret-123")

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="freelancer-default")
current_trace_id: ContextVar[str] = ContextVar("current_trace_id", default="")


def get_current_user_id() -> str:
    return current_user_id.get() or "freelancer-default"


def get_current_trace_id() -> str:
    tid = current_trace_id.get()
    if not tid:
        tid = uuid4().hex
        current_trace_id.set(tid)
    return tid


def create_mcp_server(
    store: WorkspaceStore | None = None,
) -> tuple[FastMCP, WorkspaceStore]:
    """Builds and registers tools on the FastMCP Workspace server."""
    app_store = store or WorkspaceStore()

    mcp = FastMCP("Workspace MCP Server", streamable_http_path="/mcp")

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
    )
    def list_free_slots(
        days_ahead: int = Field(
            default=3,
            ge=1,
            le=14,
            description="Number of business days ahead to query availability (1-14).",
        ),
        duration_min: int = Field(
            default=30,
            ge=15,
            le=120,
            description="Duration of interview slot in minutes (15-120).",
        ),
    ) -> ListFreeSlotsOutput:
        """Lists available free calendar slots for interview scheduling over upcoming business days.

        When to use:
        - When a client expresses interest in an interview or asks for availability.
        - To retrieve concrete time windows to propose in conversation messages.

        When NOT to use:
        - For general technical questions or proposal submissions.

        NOTE: Real Google Calendar APIs are NOT wired. Runs against local mock calendar store.
        """
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()

        slots = app_store.list_free_slots(days_ahead=days_ahead, duration_min=duration_min)
        out = ListFreeSlotsOutput(slots=slots, count=len(slots), timezone="UTC")

        app_store.record_audit(
            user_id=user_id,
            tool="list_free_slots",
            arguments={"days_ahead": days_ahead, "duration_min": duration_min},
            result=out.model_dump(),
            status="ok",
            trace_id=trace_id,
        )
        return out

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            idempotentHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
    )
    def create_tentative_hold(
        slot_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            description="Identifier of the free calendar slot to hold.",
        ),
        title: str = Field(
            ...,
            min_length=3,
            max_length=200,
            description="Context or title for tentative hold.",
        ),
        idempotency_key: str = Field(
            default="",
            max_length=128,
            description="Client idempotency key for safe retries without duplicate holds.",
        ),
    ) -> TentativeHoldOutput:
        """Places a non-destructive tentative calendar hold on a free slot during client negotiations.

        When to use:
        - ONLY after human approval has been granted to propose meeting times to a client.
        - To reserve a timeslot tentatively until the client confirms.

        When NOT to use:
        - Automatically before human sign-off.
        - If the meeting is not requested by the client.

        NOTE: Non-destructive, idempotent hold. Real Google Calendar APIs are NOT wired.
        """
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()

        out = app_store.create_tentative_hold(
            slot_id=slot_id,
            title=title,
            idempotency_key=idempotency_key,
        )

        app_store.record_audit(
            user_id=user_id,
            tool="create_tentative_hold",
            arguments={"slot_id": slot_id, "title": title, "idempotency_key": idempotency_key},
            result=out.model_dump(),
            status="ok",
            trace_id=trace_id,
        )
        return out

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            idempotentHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
    )
    def create_email_draft(
        to: str = Field(
            ...,
            min_length=3,
            max_length=254,
            description="Recipient email address.",
        ),
        subject: str = Field(
            ...,
            min_length=1,
            max_length=200,
            description="Email subject line.",
        ),
        body: str = Field(
            ...,
            min_length=1,
            max_length=10000,
            description="Draft body text.",
        ),
        idempotency_key: str = Field(
            default="",
            max_length=128,
            description="Idempotency key for draft persistence.",
        ),
    ) -> EmailDraftOutput:
        """Saves a draft client follow-up email to the mock workspace inbox/outbox.

        When to use:
        - When preparing follow-up documentation or external client communications.

        When NOT to use:
        - In-platform marketplace chats (use send_message on marketplace port instead).

        NOTE: Non-destructive, idempotent draft creation. Real Gmail APIs are NOT wired.
        """
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()

        out = app_store.create_email_draft(
            to=to,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )

        app_store.record_audit(
            user_id=user_id,
            tool="create_email_draft",
            arguments={"to": to, "subject": subject, "body": body, "idempotency_key": idempotency_key},
            result=out.model_dump(),
            status="ok",
            trace_id=trace_id,
        )
        return out

    return mcp, app_store


class WorkspaceAuthMiddleware(BaseHTTPMiddleware):
    """Bearer-token authentication middleware for Workspace MCP HTTP server."""

    def __init__(self, app: Any, expected_token: str) -> None:
        super().__init__(app)
        self.expected_token = expected_token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "detail": "Missing Bearer token in Authorization header."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if token != self.expected_token:
            return JSONResponse(
                {"error": "unauthorized", "detail": "Invalid Bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = request.headers.get("X-User-Id") or "freelancer-user-1"
        trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
        current_user_id.set(user_id)
        current_trace_id.set(trace_id)

        return await call_next(request)


def create_app(
    store: WorkspaceStore | None = None,
    token: str | None = None,
) -> Starlette:
    """Builds ASGI Starlette application with FastMCP and auth middleware."""
    mcp, _ = create_mcp_server(store=store)
    expected_token = token or DEFAULT_TOKEN

    app = mcp.streamable_http_app()
    app.add_middleware(WorkspaceAuthMiddleware, expected_token=expected_token)
    return app


# Singleton ASGI application for uvicorn
mcp_server, server_store = create_mcp_server()
app = create_app(store=server_store)


def main() -> None:
    parser = argparse.ArgumentParser(description="GigBid Workspace MCP Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP server port")
    parser.add_argument("--stdio", action="store_true", help="Run via stdio transport instead of HTTP")
    args = parser.parse_args()

    if args.stdio:
        mcp, _ = create_mcp_server()
        mcp.run(transport="stdio")
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
