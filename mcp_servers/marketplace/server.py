"""Marketplace MCP Server (FastMCP, Streamable HTTP transport).

Features:
- READ & WRITE tools with strict Pydantic constraints and output schemas.
- Comprehensive tool descriptions with explicit 'When to use' and 'When NOT to use'.
- Idempotency caching via audit store.
- Degraded mode for MarketplaceUnavailable.
- Bearer-token authentication and per-user sliding-window rate limiting.
- Append-only audit logging with PII masking.
"""
from __future__ import annotations

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

from mcp_servers.marketplace.adapters.base import (
    MarketplaceAdapter,
    MarketplaceUnavailable,
    NotFound,
    RateLimited,
    ValidationRejected,
)
from mcp_servers.marketplace.adapters.factory import get_adapter
from mcp_servers.marketplace.audit import AuditStore
from mcp_servers.marketplace.ratelimit import MarketplaceRateLimiter
from mcp_servers.marketplace.schemas import (
    ClientHistoryOutput,
    ConnectsBalanceOutput,
    ErrorOutput,
    JobItem,
    ListMessagesOutput,
    MessageItem,
    ProposalDraftOutput,
    ProposalSubmitOutput,
    SearchJobsOutput,
)

DEFAULT_PORT = 8002
DEFAULT_TOKEN = os.getenv("MARKETPLACE_MCP_TOKEN", "marketplace-dev-token-secret-123")

# Request context variables preserved across async invocations
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
    adapter: MarketplaceAdapter | None = None,
    audit_store: AuditStore | None = None,
    rate_limiter: MarketplaceRateLimiter | None = None,
) -> tuple[FastMCP, MarketplaceAdapter, AuditStore, MarketplaceRateLimiter]:
    """Builds and registers tools on FastMCP server instance."""
    app_adapter = adapter or get_adapter()
    app_audit = audit_store or AuditStore()
    max_reqs = int(os.getenv("MARKETPLACE_RATE_LIMIT", "120"))
    app_limiter = rate_limiter or MarketplaceRateLimiter(max_requests=max_reqs, window_seconds=60.0)

    mcp = FastMCP("Marketplace MCP Server", streamable_http_path="/mcp")

    # -------------------------------------------------------------------------
    # READ TOOLS
    # -------------------------------------------------------------------------

    read_annotations = ToolAnnotations(
        readOnlyHint=True,
        idempotentHint=True,
        destructiveHint=False,
        openWorldHint=True,
    )

    @mcp.tool(
        name="search_jobs",
        annotations=read_annotations,
        description=(
            "Search active marketplace job listings by keyword query, category filter, and recency.\n"
            "When to use: Use during the scouting phase to discover newly posted jobs or search jobs matching "
            "specific persona domain criteria.\n"
            "When NOT to use: Do NOT use if you already know the specific job ID (use get_job instead). "
            "Do NOT use for bidding or submitting proposals."
        ),
    )
    async def search_jobs(
        query: str | None = Field(default=None, max_length=200, description="Keyword search query."),
        category: str | None = Field(default=None, max_length=100, description="Target job category filter."),
        since: str | None = Field(default=None, max_length=50, description="ISO timestamp for recent jobs."),
        limit: int = Field(default=20, ge=1, le=50, description="Max jobs to return (1 to 50)."),
    ) -> SearchJobsOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {"query": query, "category": category, "since": since, "limit": limit}

        try:
            raw_jobs = await app_adapter.search_jobs(query=query, category=category, since=since, limit=limit)
            items = [JobItem(**j) for j in raw_jobs]
            result = SearchJobsOutput(jobs=items, total=len(items))
            app_audit.record_audit(user_id, "search_jobs", args, result.model_dump(), "success", trace_id)
            return result
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "search_jobs", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "search_jobs", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "search_jobs", args, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="get_job",
        annotations=read_annotations,
        description=(
            "Retrieve complete details for a specific marketplace job posting.\n"
            "When to use: Use when analyzing a candidate job's scope, requirements, budget type, and Connects cost.\n"
            "When NOT to use: Do NOT use for general discovery or searching without an ID (use search_jobs instead)."
        ),
    )
    async def get_job(
        job_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Unique job identifier.",
        ),
    ) -> JobItem | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {"job_id": job_id}

        try:
            raw_job = await app_adapter.get_job(job_id)
            result = JobItem(**raw_job)
            app_audit.record_audit(user_id, "get_job", args, result.model_dump(), "success", trace_id)
            return result
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "get_job", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "get_job", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "get_job", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "get_job", args, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="get_client_history",
        annotations=read_annotations,
        description=(
            "Retrieve public hiring history and reputation metrics for a client.\n"
            "When to use: Use during risk assessment and client vetting to check spend, hire rate, ratings, and payment verification.\n"
            "When NOT to use: Do NOT use if evaluating job technical fit (use get_job instead)."
        ),
    )
    async def get_client_history(
        client_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Client identifier.",
        ),
    ) -> ClientHistoryOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {"client_id": client_id}

        try:
            raw_client = await app_adapter.get_client_history(client_id)
            result = ClientHistoryOutput(**raw_client)
            app_audit.record_audit(user_id, "get_client_history", args, result.model_dump(), "success", trace_id)
            return result
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "get_client_history", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "get_client_history", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "get_client_history", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "get_client_history", args, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="get_connects_balance",
        annotations=read_annotations,
        description=(
            "Check current available Connects balance for proposal submissions.\n"
            "When to use: Use during pricing and proposal planning to verify sufficient Connects before preparing bids.\n"
            "When NOT to use: Do NOT use repeatedly in tight loops; query once during job evaluation."
        ),
    )
    async def get_connects_balance() -> ConnectsBalanceOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()

        try:
            raw_bal = await app_adapter.get_connects_balance()
            balance = raw_bal.get("balance")
            if balance is None:
                balance = raw_bal.get("connects_balance", 0)
            result = ConnectsBalanceOutput(balance=int(balance))
            app_audit.record_audit(user_id, "get_connects_balance", {}, result.model_dump(), "success", trace_id)
            return result
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "get_connects_balance", {}, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "get_connects_balance", {}, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "get_connects_balance", {}, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="list_messages",
        annotations=read_annotations,
        description=(
            "Retrieve message history for an active client conversation.\n"
            "When to use: Use during client liaison interactions to read client questions, feedback, or interview invitations.\n"
            "When NOT to use: Do NOT use on closed proposals or when initiating a first bid."
        ),
    )
    async def list_messages(
        conversation_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Conversation thread identifier.",
        ),
    ) -> ListMessagesOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {"conversation_id": conversation_id}

        try:
            raw_msgs = await app_adapter.list_messages(conversation_id)
            items = [MessageItem(**m) for m in raw_msgs]
            result = ListMessagesOutput(conversation_id=conversation_id, messages=items)
            app_audit.record_audit(user_id, "list_messages", args, result.model_dump(), "success", trace_id)
            return result
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "list_messages", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "list_messages", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "list_messages", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "list_messages", args, err.model_dump(), "error", trace_id)
            return err

    # -------------------------------------------------------------------------
    # WRITE TOOLS
    # -------------------------------------------------------------------------

    @mcp.tool(
        name="create_proposal_draft",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
        ),
        description=(
            "Create a draft proposal or dry-run preview for an approved job posting.\n"
            "When to use: Use after risk and fit checks to persist a proposal draft or preview Connects cost with dry_run=True. Never spends Connects.\n"
            "When NOT to use: Do NOT use for initial job scouting or without an approved cover letter. Does NOT submit the proposal."
        ),
    )
    async def create_proposal_draft(
        job_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Target job identifier.",
        ),
        cover_letter: str = Field(
            ...,
            min_length=10,
            max_length=10000,
            description="Full proposal cover letter.",
        ),
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = Field(
            ...,
            gt=0.0,
            le=500_000.0,
            description="Proposed project or hourly bid in USD.",
        ),
        idempotency_key: str = Field(
            ...,
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9_.:-]+$",
            description="Idempotency key to prevent duplicate drafts.",
        ),
        dry_run: bool = Field(
            default=False,
            description="If true, returns preview with Connects cost without creating record.",
        ),
    ) -> ProposalDraftOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {
            "job_id": job_id,
            "cover_letter": cover_letter,
            "screening_answers": screening_answers,
            "bid_amount": bid_amount,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }

        # Check local idempotency cache
        if not dry_run:
            cached = app_audit.get_cached_idempotent_result(idempotency_key, "create_proposal_draft")
            if cached:
                cached_res = ProposalDraftOutput(**cached)
                app_audit.record_audit(user_id, "create_proposal_draft", args, cached, "cached", trace_id)
                return cached_res

        try:
            raw_draft = await app_adapter.create_proposal_draft(
                job_id=job_id,
                cover_letter=cover_letter,
                screening_answers=screening_answers,
                bid_amount=bid_amount,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            )
            result = ProposalDraftOutput(**raw_draft)
            if not dry_run:
                app_audit.store_idempotent_result(idempotency_key, "create_proposal_draft", result.model_dump())
            app_audit.record_audit(user_id, "create_proposal_draft", args, result.model_dump(), "success", trace_id)
            return result
        except ValidationRejected as exc:
            err = ErrorOutput(error="validation_rejected", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "create_proposal_draft", args, err.model_dump(), "rejected", trace_id)
            return err
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "create_proposal_draft", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "create_proposal_draft", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "create_proposal_draft", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "create_proposal_draft", args, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="submit_proposal",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
        ),
        description=(
            "Submit a draft proposal to the marketplace, spending Connects.\n"
            "When to use: Use ONLY during the final human-approved submission phase to formally transmit a bid and charge Connects (or preview with dry_run=True).\n"
            "When NOT to use: Do NOT use during analysis, drafting, or unapproved evaluation. Destructive: spends real Connects."
        ),
    )
    async def submit_proposal(
        proposal_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Draft proposal identifier.",
        ),
        idempotency_key: str = Field(
            ...,
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9_.:-]+$",
            description="Idempotency key to prevent double charge.",
        ),
        dry_run: bool = Field(
            default=False,
            description="If true, returns preview with Connects cost without deducting Connects.",
        ),
    ) -> ProposalSubmitOutput | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {
            "proposal_id": proposal_id,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }

        # Check local idempotency cache
        if not dry_run:
            cached = app_audit.get_cached_idempotent_result(idempotency_key, "submit_proposal")
            if cached:
                cached_res = ProposalSubmitOutput(**cached)
                app_audit.record_audit(user_id, "submit_proposal", args, cached, "cached", trace_id)
                return cached_res

        try:
            raw_submit = await app_adapter.submit_proposal(
                proposal_id=proposal_id,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            )
            result = ProposalSubmitOutput(**raw_submit)
            if not dry_run:
                app_audit.store_idempotent_result(idempotency_key, "submit_proposal", result.model_dump())
            app_audit.record_audit(user_id, "submit_proposal", args, result.model_dump(), "success", trace_id)
            return result
        except ValidationRejected as exc:
            err = ErrorOutput(error="validation_rejected", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "submit_proposal", args, err.model_dump(), "rejected", trace_id)
            return err
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "submit_proposal", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "submit_proposal", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "submit_proposal", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "submit_proposal", args, err.model_dump(), "error", trace_id)
            return err

    @mcp.tool(
        name="send_message",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
        ),
        description=(
            "Send a message to a client in an active conversation thread.\n"
            "When to use: Use during negotiation or client inquiries to reply to client questions or schedule interviews.\n"
            "When NOT to use: Do NOT use for initial proposal submission (use submit_proposal instead)."
        ),
    )
    async def send_message(
        conversation_id: str = Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Conversation thread identifier.",
        ),
        text: str = Field(
            ...,
            min_length=1,
            max_length=5000,
            description="Message body text.",
        ),
        idempotency_key: str = Field(
            ...,
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9_.:-]+$",
            description="Idempotency key to prevent duplicate messages.",
        ),
        dry_run: bool = Field(
            default=False,
            description="If true, returns preview without sending message.",
        ),
    ) -> MessageItem | ErrorOutput:
        user_id = get_current_user_id()
        trace_id = get_current_trace_id()
        args = {
            "conversation_id": conversation_id,
            "text": text,
            "idempotency_key": idempotency_key,
            "dry_run": dry_run,
        }

        # Check local idempotency cache
        if not dry_run:
            cached = app_audit.get_cached_idempotent_result(idempotency_key, "send_message")
            if cached:
                cached_res = MessageItem(**cached)
                app_audit.record_audit(user_id, "send_message", args, cached, "cached", trace_id)
                return cached_res

        try:
            raw_msg = await app_adapter.send_message(
                conversation_id=conversation_id,
                text=text,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            )
            result = MessageItem(**raw_msg)
            if not dry_run:
                app_audit.store_idempotent_result(idempotency_key, "send_message", result.model_dump())
            app_audit.record_audit(user_id, "send_message", args, result.model_dump(), "success", trace_id)
            return result
        except NotFound as exc:
            err = ErrorOutput(error="not_found", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "send_message", args, err.model_dump(), "not_found", trace_id)
            return err
        except MarketplaceUnavailable as exc:
            err = ErrorOutput(error="marketplace_unavailable", retryable=True, detail=str(exc))
            app_audit.record_audit(user_id, "send_message", args, err.model_dump(), "degraded", trace_id)
            return err
        except RateLimited as exc:
            err = ErrorOutput(error="rate_limited", retryable=True, retry_after=exc.retry_after, detail=str(exc))
            app_audit.record_audit(user_id, "send_message", args, err.model_dump(), "rate_limited", trace_id)
            return err
        except Exception as exc:  # noqa: BLE001
            err = ErrorOutput(error="internal_error", retryable=False, detail=str(exc))
            app_audit.record_audit(user_id, "send_message", args, err.model_dump(), "error", trace_id)
            return err

    return mcp, app_adapter, app_audit, app_limiter


# -----------------------------------------------------------------------------
# HTTP Server & Auth Middleware
# -----------------------------------------------------------------------------

class MarketplaceAuthMiddleware(BaseHTTPMiddleware):
    """Enforces Bearer authentication, extracts context, and applies per-user rate limiting."""

    def __init__(
        self,
        app: Any,
        expected_token: str,
        rate_limiter: MarketplaceRateLimiter,
    ) -> None:
        super().__init__(app)
        self.expected_token = expected_token
        self.rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Ignore CORS preflight
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

        # Context extraction
        user_id = request.headers.get("X-User-Id") or "freelancer-user-1"
        trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
        current_user_id.set(user_id)
        current_trace_id.set(trace_id)

        # Per-user rate limiting check
        allowed, retry_after = self.rate_limiter.check(user_id)
        if not allowed:
            return JSONResponse(
                {
                    "error": "rate_limited",
                    "retryable": True,
                    "retry_after": retry_after,
                    "detail": f"Per-user rate limit exceeded. Retry after {retry_after}s.",
                },
                status_code=429,
                headers={"Retry-After": str(int(retry_after))},
            )

        return await call_next(request)


def create_app(
    adapter: MarketplaceAdapter | None = None,
    audit_store: AuditStore | None = None,
    rate_limiter: MarketplaceRateLimiter | None = None,
    token: str | None = None,
) -> Starlette:
    """Builds ASGI Starlette application with auth and rate limiting middleware."""
    mcp, _, _, limiter = create_mcp_server(
        adapter=adapter,
        audit_store=audit_store,
        rate_limiter=rate_limiter,
    )

    expected_token = token or DEFAULT_TOKEN
    app = mcp.streamable_http_app()
    app.add_middleware(
        MarketplaceAuthMiddleware,
        expected_token=expected_token,
        rate_limiter=limiter,
    )
    return app


# Default singleton instance for ASGI runners (uvicorn mcp_servers.marketplace.server:app)
mcp_server, server_adapter, server_audit, server_limiter = create_mcp_server()
app = create_app(
    adapter=server_adapter,
    audit_store=server_audit,
    rate_limiter=server_limiter,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)
