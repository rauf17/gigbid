"""MarketplacePort Protocol and McpMarketplacePort implementation.

Requirements R1 / A2:
- Single internal port for all marketplace operations.
- Mediated strictly through MCP tools via MultiServerMCPClient.
- Zero direct HTTP client or simulator imports in agent codebase.
- Typed exceptions returned for all server error responses.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.marketplace_models import (
    ClientHistory,
    ConnectsBalance,
    Job,
    Message,
    ProposalDraft,
    ProposalSubmit,
)


class MarketplacePortError(Exception):
    """Base exception for all MarketplacePort operations."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class MarketplaceUnavailable(MarketplacePortError):
    """Raised when marketplace MCP server reports backend is unreachable or degraded."""

    def __init__(self, message: str = "Marketplace service unavailable", retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class RateLimited(MarketplacePortError):
    """Raised when marketplace or adapter rate limit has been exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NotFound(MarketplacePortError):
    """Raised when a job, client, proposal, or conversation is not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ValidationRejected(MarketplacePortError):
    """Raised when proposal content or parameters violate marketplace policy."""

    def __init__(self, message: str = "Validation rejected by marketplace", detail: str | None = None) -> None:
        super().__init__(message, detail)


class MarketplacePort(ABC):
    """Abstract interface defining the internal marketplace contract for agent graphs."""

    @abstractmethod
    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[Job]:
        """Search jobs matching optional keywords and criteria."""

    @abstractmethod
    async def get_job(self, job_id: str) -> Job:
        """Fetch full details for a candidate job."""

    @abstractmethod
    async def get_client_history(self, client_id: str) -> ClientHistory:
        """Fetch client spending, hire rate, and feedback metrics."""

    @abstractmethod
    async def get_connects_balance(self) -> ConnectsBalance:
        """Check current Connects balance."""

    @abstractmethod
    async def list_messages(self, conversation_id: str) -> list[Message]:
        """List messages in an active conversation thread."""

    @abstractmethod
    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> ProposalDraft:
        """Create a proposal draft (or preview Connects cost with dry_run=True)."""

    @abstractmethod
    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> ProposalSubmit:
        """Submit an approved proposal draft to spend Connects (or preview with dry_run=True)."""

    @abstractmethod
    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> Message:
        """Send a message to an active conversation thread."""


class McpMarketplacePort(MarketplacePort):
    """Implementation of MarketplacePort calling the Marketplace MCP server."""

    def __init__(
        self,
        server_url: str | None = None,
        token: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        client: MultiServerMCPClient | None = None,
        in_memory_session: Any | None = None,
    ) -> None:
        self.server_url = (server_url or os.getenv("MARKETPLACE_MCP_URL") or "http://127.0.0.1:8002").rstrip("/")
        self.token = token or os.getenv("MARKETPLACE_MCP_TOKEN") or "marketplace-dev-token-secret-123"
        self.trace_id = trace_id or uuid4().hex
        self.user_id = user_id or "freelancer-user-1"
        self._in_memory_session = in_memory_session

        if client is not None:
            self._client = client
        elif in_memory_session is None:
            endpoint_url = f"{self.server_url}/mcp" if not self.server_url.endswith("/mcp") else self.server_url
            self._client = MultiServerMCPClient(
                connections={
                    "marketplace": {
                        "transport": "streamable_http",
                        "url": endpoint_url,
                        "headers": {
                            "Authorization": f"Bearer {self.token}",
                            "X-Trace-Id": self.trace_id,
                            "X-User-Id": self.user_id,
                        },
                    }
                }
            )
        else:
            self._client = None

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invokes tool through MCP session and unwraps typed results or errors."""
        if self._in_memory_session is not None:
            raw_res = await self._in_memory_session.call_tool(tool_name, arguments)
            return self._parse_tool_result(raw_res)

        async with self._client.session("marketplace") as session:
            raw_res = await session.call_tool(tool_name, arguments)
            return self._parse_tool_result(raw_res)

    def _parse_tool_result(self, raw_res: Any) -> Any:
        content_items = getattr(raw_res, "content", [])
        is_error = getattr(raw_res, "isError", False)

        text = ""
        for item in content_items:
            if hasattr(item, "text"):
                text += item.text

        if is_error:
            if "validation error" in text.lower():
                raise ValidationRejected(f"MCP schema validation rejected: {text}", detail=text)
            if "marketplace_unavailable" in text.lower():
                raise MarketplaceUnavailable(f"Marketplace unavailable: {text}")
            if "rate_limited" in text.lower():
                raise RateLimited(f"Rate limited: {text}")
            if "not_found" in text.lower():
                raise NotFound(f"Resource not found: {text}")
            raise MarketplacePortError(f"MCP execution error: {text}")

        parsed_data: Any = None
        if text:
            try:
                parsed_data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                parsed_data = text

        # Check for structured error responses returned as result
        if isinstance(parsed_data, dict) and "error" in parsed_data:
            err_code = parsed_data.get("error")
            detail = parsed_data.get("detail", "")
            if err_code == "marketplace_unavailable":
                raise MarketplaceUnavailable(f"Marketplace unavailable: {detail}", retryable=True)
            elif err_code == "rate_limited":
                retry_after = float(parsed_data.get("retry_after", 60.0))
                raise RateLimited(f"Rate limited: {detail}", retry_after=retry_after)
            elif err_code == "not_found":
                raise NotFound(f"Resource not found: {detail}")
            elif err_code == "validation_rejected":
                raise ValidationRejected(f"Validation rejected: {detail}", detail=detail)
            else:
                raise MarketplacePortError(f"Marketplace error ({err_code}): {detail}")

        return parsed_data

    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[Job]:
        data = await self._call_tool(
            "search_jobs",
            {"query": query, "category": category, "since": since, "limit": limit},
        )
        if isinstance(data, dict):
            raw_list = data.get("jobs", [])
            return [Job(**item) for item in raw_list]
        return []

    async def get_job(self, job_id: str) -> Job:
        data = await self._call_tool("get_job", {"job_id": job_id})
        if isinstance(data, dict):
            return Job(**data)
        raise MarketplacePortError(f"Unexpected get_job response: {data}")

    async def get_client_history(self, client_id: str) -> ClientHistory:
        data = await self._call_tool("get_client_history", {"client_id": client_id})
        if isinstance(data, dict):
            return ClientHistory(**data)
        raise MarketplacePortError(f"Unexpected get_client_history response: {data}")

    async def get_connects_balance(self) -> ConnectsBalance:
        data = await self._call_tool("get_connects_balance", {})
        if isinstance(data, dict):
            return ConnectsBalance(**data)
        raise MarketplacePortError(f"Unexpected get_connects_balance response: {data}")

    async def list_messages(self, conversation_id: str) -> list[Message]:
        data = await self._call_tool("list_messages", {"conversation_id": conversation_id})
        if isinstance(data, dict):
            raw_msgs = data.get("messages", [])
            return [Message(**item) for item in raw_msgs]
        return []

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> ProposalDraft:
        data = await self._call_tool(
            "create_proposal_draft",
            {
                "job_id": job_id,
                "cover_letter": cover_letter,
                "screening_answers": screening_answers,
                "bid_amount": bid_amount,
                "idempotency_key": idempotency_key,
                "dry_run": dry_run,
            },
        )
        if isinstance(data, dict):
            return ProposalDraft(**data)
        raise MarketplacePortError(f"Unexpected create_proposal_draft response: {data}")

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> ProposalSubmit:
        data = await self._call_tool(
            "submit_proposal",
            {
                "proposal_id": proposal_id,
                "idempotency_key": idempotency_key,
                "dry_run": dry_run,
            },
        )
        if isinstance(data, dict):
            return ProposalSubmit(**data)
        raise MarketplacePortError(f"Unexpected submit_proposal response: {data}")

    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> Message:
        data = await self._call_tool(
            "send_message",
            {
                "conversation_id": conversation_id,
                "text": text,
                "idempotency_key": idempotency_key,
                "dry_run": dry_run,
            },
        )
        if isinstance(data, dict):
            return Message(**data)
        raise MarketplacePortError(f"Unexpected send_message response: {data}")
