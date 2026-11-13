"""Base Marketplace Adapter interface and typed exceptions.

Requirement R1 / A2: All marketplace interaction is mediated through adapters
implementing this abstract interface. No direct external calls in agent graphs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketplaceError(Exception):
    """Base exception for all marketplace adapter errors."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class MarketplaceUnavailable(MarketplaceError):
    """Raised when marketplace service is unreachable, timed out, or 5xx after retries."""

    def __init__(
        self,
        message: str = "Marketplace service is unavailable",
        retryable: bool = True,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail)
        self.retryable = retryable


class RateLimited(MarketplaceError):
    """Raised when marketplace or adapter rate limit has been exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float = 60.0,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail)
        self.retry_after = retry_after


class NotFound(MarketplaceError):
    """Raised when a requested resource (job, client, proposal, conversation) is not found."""

    def __init__(self, message: str = "Resource not found", detail: str | None = None) -> None:
        super().__init__(message, detail)


class ValidationRejected(MarketplaceError):
    """Raised when an operation is rejected by marketplace policy, schema, or banned phrases."""

    def __init__(
        self,
        message: str = "Request rejected by validation policy",
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail)


class MarketplaceAdapter(ABC):
    """Abstract interface defining the contract for marketplace adapters (GigSim or live Upwork)."""

    @abstractmethod
    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search jobs matching optional query keyword, category filter, and recency."""

    @abstractmethod
    async def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch details for a specific job."""

    @abstractmethod
    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        """Fetch public hiring history and reputation for a client."""

    @abstractmethod
    async def get_connects_balance(self) -> dict[str, Any]:
        """Fetch current available Connects balance."""

    @abstractmethod
    async def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """List messages in an active conversation."""

    @abstractmethod
    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create a proposal draft or preview (dry_run). Never spends Connects."""

    @abstractmethod
    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Submit a proposal draft and spend Connects (or preview if dry_run=True)."""

    @abstractmethod
    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Send a message to a client conversation (or preview if dry_run=True)."""
