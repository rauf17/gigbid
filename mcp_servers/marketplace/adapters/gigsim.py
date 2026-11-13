"""GigSim REST client implementation of MarketplaceAdapter.

Features:
- Bounded retries (max 3) with exponential backoff and jitter on 5xx, timeouts, and 429.
- Preservation of Idempotency-Key across write retries.
- Typed error mappings (MarketplaceUnavailable, RateLimited, NotFound, ValidationRejected).
- Full dry_run support without spending Connects.
"""
from __future__ import annotations

import asyncio
import os
import random
from datetime import UTC, datetime
from typing import Any, Self

import httpx

from mcp_servers.marketplace.adapters.base import (
    MarketplaceAdapter,
    MarketplaceUnavailable,
    NotFound,
    RateLimited,
    ValidationRejected,
)


class GigSimAdapter(MarketplaceAdapter):
    """Adapter for interacting with student-built GigSim server via REST."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
    ) -> None:
        self.base_url = (base_url or os.getenv("GIGSIM_API_URL") or "http://127.0.0.1:8081").rstrip("/")
        self.token = token or os.getenv("GIGSIM_API_TOKEN") or "gigsim-dev-token-secret-xyz"
        self.max_retries = max_retries

        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(10.0, connect=3.0),
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def close(self) -> None:
        """Close internal HTTP client if owned."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        req_headers = dict(headers or {})
        if idempotency_key:
            req_headers["Idempotency-Key"] = idempotency_key

        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 404:
                    detail = response.text
                    try:
                        parsed = response.json()
                        if isinstance(parsed, dict) and "detail" in parsed:
                            detail = str(parsed["detail"])
                    except (ValueError, TypeError):
                        detail = response.text
                    raise NotFound(f"Resource not found at {path}: {detail}", detail=detail)

                if response.status_code == 400:
                    detail = response.text
                    try:
                        parsed = response.json()
                        if isinstance(parsed, dict) and "detail" in parsed:
                            detail = str(parsed["detail"])
                    except (ValueError, TypeError):
                        detail = response.text
                    raise ValidationRejected(
                        f"Validation rejected by marketplace: {detail}", detail=detail
                    )

                if response.status_code == 429:
                    retry_after_str = response.headers.get("Retry-After", "5")
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        retry_after = 5.0

                    if attempt < self.max_retries and retry_after <= 5.0:
                        backoff = retry_after + random.uniform(0.05, 0.2)
                        await asyncio.sleep(backoff)
                        continue

                    raise RateLimited(
                        f"Marketplace rate limit exceeded. Retry after {retry_after}s.",
                        retry_after=retry_after,
                        detail=response.text,
                    )

                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        backoff = 0.2 * (2**attempt) + random.uniform(0.01, 0.1)
                        await asyncio.sleep(backoff)
                        continue
                    raise MarketplaceUnavailable(
                        f"GigSim server error {response.status_code} at {path} after retries.",
                        retryable=True,
                        detail=response.text,
                    )

                if response.status_code == 401:
                    raise MarketplaceUnavailable(
                        "GigSim authorization failed. Check GIGSIM_API_TOKEN.",
                        retryable=False,
                        detail=response.text,
                    )

                # Other 4xx client errors
                response.raise_for_status()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    backoff = 0.2 * (2**attempt) + random.uniform(0.01, 0.1)
                    await asyncio.sleep(backoff)
                    continue
                raise MarketplaceUnavailable(
                    f"GigSim communication failed after {self.max_retries} retries: {exc}",
                    retryable=True,
                ) from exc

        raise MarketplaceUnavailable(
            f"Request to {path} exhausted retries: {last_exc}",
            retryable=True,
        )

    async def search_jobs(
        self,
        query: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor

        data = await self._request_with_retry("GET", "/jobs", params=params)
        if isinstance(data, dict):
            return data.get("items", [])
        return data if isinstance(data, list) else []

    async def get_job(self, job_id: str) -> dict[str, Any]:
        data = await self._request_with_retry("GET", f"/jobs/{job_id}")
        return data if isinstance(data, dict) else {}

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        data = await self._request_with_retry("GET", f"/clients/{client_id}")
        return data if isinstance(data, dict) else {}

    async def get_connects_balance(self) -> dict[str, Any]:
        data = await self._request_with_retry("GET", "/connects/balance")
        return data if isinstance(data, dict) else {"connects_balance": 0}

    async def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        data = await self._request_with_retry(
            "GET", f"/conversations/{conversation_id}/messages"
        )
        return data if isinstance(data, list) else []

    async def create_proposal_draft(
        self,
        job_id: str,
        cover_letter: str,
        screening_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
        bid_amount: float = 0.0,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "cover_letter": cover_letter,
            "bid_amount": bid_amount,
            "dry_run": dry_run,
        }
        if screening_answers:
            payload["screening_answers"] = screening_answers

        data = await self._request_with_retry(
            "POST",
            "/proposals",
            json_data=payload,
            idempotency_key=idempotency_key,
        )
        return data if isinstance(data, dict) else {}

    async def submit_proposal(
        self,
        proposal_id: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            # In dry_run, check proposal existence and balance without calling /submit
            all_proposals = await self._request_with_retry("GET", "/proposals")
            target = next((p for p in all_proposals if p.get("id") == proposal_id), None)
            if not target:
                raise NotFound(f"Proposal {proposal_id} not found.")

            balance_data = await self.get_connects_balance()
            balance = balance_data.get("balance")
            if balance is None:
                balance = balance_data.get("connects_balance", 0)
            cost = target.get("connects_cost", 0)

            return {
                "id": proposal_id,
                "job_id": target.get("job_id", ""),
                "status": target.get("status", "draft"),
                "connects_cost": cost,
                "connects_balance": balance,
                "submitted_at": None,
                "dry_run": True,
                "message": f"Dry run: proposal {proposal_id} would be submitted for {cost} Connects. Nothing charged.",
            }

        data = await self._request_with_retry(
            "POST",
            f"/proposals/{proposal_id}/submit",
            idempotency_key=idempotency_key,
        )
        if isinstance(data, dict):
            data["dry_run"] = False
            return data
        return {}

    async def send_message(
        self,
        conversation_id: str,
        text: str,
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            # Verify conversation exists
            await self.list_messages(conversation_id)
            now_iso = datetime.now(UTC).isoformat()
            return {
                "id": f"dry_run_msg_{conversation_id}",
                "conversation_id": conversation_id,
                "sender": "freelancer",
                "text": text,
                "created_at": now_iso,
                "dry_run": True,
                "message": "Dry run: message preview generated, nothing sent.",
            }

        data = await self._request_with_retry(
            "POST",
            f"/conversations/{conversation_id}/messages",
            json_data={"text": text},
            idempotency_key=idempotency_key,
        )
        if isinstance(data, dict):
            data["dry_run"] = False
            return data
        return {}
