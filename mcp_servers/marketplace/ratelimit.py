"""Sliding-window per-user rate limiter for Marketplace MCP server."""
from __future__ import annotations

import math
import time
from collections import defaultdict


class MarketplaceRateLimiter:
    """In-memory sliding window rate limiter per user.

    Defaults to 20 requests per minute to stay safely below GigSim's 30 req/min limit.
    """

    def __init__(self, max_requests: int = 20, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> tuple[bool, float]:
        """Checks if a user is within their rate limit.

        Returns (allowed, retry_after_seconds).
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune expired timestamps
        history = [ts for ts in self._history[user_id] if ts > cutoff]
        self._history[user_id] = history

        if len(history) >= self.max_requests:
            oldest = history[0]
            retry_after = max(1.0, math.ceil(self.window_seconds - (now - oldest)))
            return False, float(retry_after)

        self._history[user_id].append(now)
        return True, 0.0

    def reset(self) -> None:
        """Clears all rate limit histories (used in test teardown)."""
        self._history.clear()
