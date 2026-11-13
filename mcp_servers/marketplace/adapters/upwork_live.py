"""Live Upwork adapter stub (AI-4016 GigBid Phase later).

Implementing this interface satisfies requirement R1 / A2 so switching
to a live Upwork OAuth integration requires zero architectural changes to agent graphs.
"""
from __future__ import annotations

from typing import Any

from mcp_servers.marketplace.adapters.base import MarketplaceAdapter


class UpworkLiveAdapter(MarketplaceAdapter):
    """Stub adapter for live Upwork API integration planned for future extension."""

    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def get_job(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def get_connects_balance(self) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")

    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError("live Upwork adapter: Phase later")
