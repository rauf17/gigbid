"""FastAPI application entrypoint for GigBid."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.db import init_db
from apps.api.auth.router import router as auth_router
from apps.api.auth.service import seed_reviewer_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize DB schemas if possible
    init_db()
    # Seed reviewer user
    seed_reviewer_user()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="GigBid API",
        description="Autonomous freelancer copilot backend API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    return app


app = create_app()
