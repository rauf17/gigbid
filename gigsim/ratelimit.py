"""Rate Limiting, Authentication, and Fault Injection Middleware for GigSim.

Implements:
  - Bearer token authentication against GIGSIM_API_TOKEN
  - Token-bucket sliding window rate limiter (default 30 req/min) returning 429 with Retry-After
  - Configurable transient fault injection (default 3% 500 errors)
  - Optional artificial latency simulation

All limits and rates are configured in gigsim/seed/platform_rules.yaml.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import Callable

import yaml
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}
ADMIN_PREFIX = "/admin/"


class GigSimMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rules_path: str | None = None) -> None:
        super().__init__(app)
        self.rules_path = rules_path
        self._load_rules()
        self.request_timestamps: dict[str, list[float]] = {}

    def _load_rules(self) -> None:
        """Loads platform rules from YAML."""
        self.rate_limit_per_minute = 30
        self.retry_after_seconds = 60
        self.fault_injection_rate = 0.03
        self.latency_ms = 0

        if self.rules_path and os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    rules = yaml.safe_load(f) or {}
                limits = rules.get("limits", {})
                self.rate_limit_per_minute = limits.get("rate_limit_per_minute", 30)
                self.retry_after_seconds = limits.get("retry_after_seconds", 60)

                simulation = rules.get("simulation", {})
                self.fault_injection_rate = simulation.get("fault_injection_rate", 0.03)
                self.latency_ms = simulation.get("latency_ms", 0)
            except (OSError, yaml.YAMLError) as e:
                print(f"[ratelimit] Warning loading rules YAML: {e}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Health check and OpenAPI docs pass through directly
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # 2. Bearer Token Authentication
        expected_token = os.environ.get("GIGSIM_API_TOKEN")
        if expected_token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Bearer authentication header."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            token = auth_header[7:].strip()
            if token != expected_token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid API token."},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Admin routes bypass rate limiting and simulated transient faults
        if path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        # 3. Rate Limiting (Sliding Window: 60 seconds)
        enforce_rate_limit = (
            os.environ.get("GIGSIM_TESTING") != "1"
            or os.environ.get("GIGSIM_TEST_RATE_LIMIT") == "1"
        )
        if enforce_rate_limit:
            client_key = request.headers.get("Authorization", request.client.host if request.client else "default")
            now = time.time()
            window_start = now - 60.0

            timestamps = self.request_timestamps.setdefault(client_key, [])
            # Prune old timestamps
            self.request_timestamps[client_key] = [t for t in timestamps if t > window_start]

            if len(self.request_timestamps[client_key]) >= self.rate_limit_per_minute:
                oldest = self.request_timestamps[client_key][0]
                retry_after = max(1, int(oldest + 60.0 - now))
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded ({self.rate_limit_per_minute} req/min). Try again later."},
                    headers={"Retry-After": str(retry_after)},
                )

            self.request_timestamps[client_key].append(now)

        # 4. Simulated Transient Fault Injection (Default 3% 500 error, disabled in test mode)
        fault_rate = self.fault_injection_rate
        if os.environ.get("GIGSIM_FAULT_RATE") is not None:
            try:
                fault_rate = float(os.environ["GIGSIM_FAULT_RATE"])
            except ValueError:
                pass
        elif os.environ.get("GIGSIM_TESTING") == "1":
            fault_rate = 0.0

        if fault_rate > 0.0 and random.random() < fault_rate:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error (Simulated Transient Fault)."},
            )

        # 5. Simulated Artificial Latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        return await call_next(request)
