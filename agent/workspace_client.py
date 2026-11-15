"""Client adapter for Workspace MCP server and local mock storage."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp_servers.workspace.schemas import (
    EmailDraftOutput,
    TentativeHoldOutput,
    TimeSlot,
)
from mcp_servers.workspace.store import WorkspaceStore


class WorkspaceClient(ABC):
    """Abstract interface for Workspace calendar and email tools."""

    @abstractmethod
    async def list_free_slots(self, days_ahead: int = 3, duration_min: int = 30) -> list[dict[str, Any]]:
        """Lists available interview meeting slots."""

    @abstractmethod
    async def create_tentative_hold(
        self,
        slot_id: str,
        title: str,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Places a tentative hold on a meeting slot."""

    @abstractmethod
    async def create_email_draft(
        self,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Creates an email draft."""


class MockWorkspaceClient(WorkspaceClient):
    """Direct in-process client wrapping WorkspaceStore without network overhead."""

    def __init__(self, store: WorkspaceStore | None = None) -> None:
        self.store = store or WorkspaceStore()

    async def list_free_slots(self, days_ahead: int = 3, duration_min: int = 30) -> list[dict[str, Any]]:
        slots: list[TimeSlot] = self.store.list_free_slots(days_ahead=days_ahead, duration_min=duration_min)
        return [s.model_dump() for s in slots]

    async def create_tentative_hold(
        self,
        slot_id: str,
        title: str,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        hold: TentativeHoldOutput = self.store.create_tentative_hold(
            slot_id=slot_id,
            title=title,
            idempotency_key=idempotency_key,
        )
        return hold.model_dump()

    async def create_email_draft(
        self,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        draft: EmailDraftOutput = self.store.create_email_draft(
            to=to,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )
        return draft.model_dump()


def get_workspace_client(store: WorkspaceStore | None = None) -> WorkspaceClient:
    """Returns the active WorkspaceClient. Defaults to hermetic in-process MockWorkspaceClient."""
    return MockWorkspaceClient(store=store)
