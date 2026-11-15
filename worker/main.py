"""Arq worker entrypoint and settings."""
from __future__ import annotations

import logging
import os
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from agent.db import init_db
from worker.tasks import analyse_job, cron_scout_all, scout_saved_search

logger = logging.getLogger("gigbid.worker")


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("[worker] GigBid Arq worker starting up...")
    init_db()


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("[worker] GigBid Arq worker shutting down cleanly...")


class WorkerSettings:
    """Settings class consumed by `arq worker.main.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [scout_saved_search, analyse_job]
    cron_jobs: ClassVar[list[Any]] = [cron(cron_scout_all, minute={0, 15, 30, 45})]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0"))
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 600
