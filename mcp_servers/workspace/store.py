"""Local mock calendar and email store for Workspace MCP server.

NOTE: Real Google APIs (Calendar, Gmail) are NOT wired to external networks.
This server operates over a deterministic local mock store for assignment compliance.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.pii import mask_pii_obj
from mcp_servers.workspace.schemas import (
    EmailDraftOutput,
    TentativeHoldOutput,
    TimeSlot,
)

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path(__file__).resolve().parent / "state"


class WorkspaceStore:
    """Thread-safe local mock storage for calendar slots, tentative holds, and email drafts."""

    def __init__(self, state_dir: Path | str | None = None) -> None:
        self.state_dir = Path(state_dir or DEFAULT_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.state_dir / "workspace_state.json"
        self.db_path = self.state_dir / "audit.db"

        self._init_audit_db()
        self._load_state()

    # -------------------------------------------------------------------------
    # Audit DB & Idempotency
    # -------------------------------------------------------------------------

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_audit_db(self) -> None:
        with self._connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                user_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                status TEXT NOT NULL,
                trace_id TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_cache (
                key TEXT PRIMARY KEY,
                tool TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def record_audit(
        self,
        user_id: str,
        tool: str,
        arguments: dict[str, Any],
        result: Any,
        status: str,
        trace_id: str,
    ) -> None:
        """Appends an execution record to the audit log after PII masking."""
        now_iso = datetime.now(UTC).isoformat()
        masked_args = mask_pii_obj(arguments)
        masked_res = mask_pii_obj(result)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (ts, user_id, tool, arguments_json, result_json, status, trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    user_id,
                    tool,
                    json.dumps(masked_args, sort_keys=True),
                    json.dumps(masked_res, sort_keys=True, default=str),
                    status,
                    trace_id,
                ),
            )
            conn.commit()

    def check_idempotency(self, key: str, tool: str) -> dict[str, Any] | None:
        """Checks whether an idempotent write operation was previously executed."""
        if not key:
            return None
        with self._connection() as conn:
            row = conn.execute(
                "SELECT result_json FROM idempotency_cache WHERE key = ? AND tool = ?",
                (key, tool),
            ).fetchone()
            if row:
                return json.loads(row["result_json"])
        return None

    def store_idempotency(self, key: str, tool: str, result: dict[str, Any]) -> None:
        """Stores idempotent outcome for replay protection."""
        if not key:
            return
        now_iso = datetime.now(UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency_cache (key, tool, result_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, tool, json.dumps(result, sort_keys=True, default=str), now_iso),
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Mock State Persistence
    # -------------------------------------------------------------------------

    def _load_state(self) -> None:
        if self.json_path.exists():
            try:
                self.state = json.loads(self.json_path.read_text(encoding="utf-8"))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Corrupted workspace state, re-initializing: %s", exc)

        self.state = {
            "holds": {},
            "drafts": {},
            "busy_blocks": [],
        }
        self._save_state()

    def _save_state(self) -> None:
        self.json_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    # -------------------------------------------------------------------------
    # Core Mock Operations
    # -------------------------------------------------------------------------

    def list_free_slots(self, days_ahead: int = 3, duration_min: int = 30) -> list[TimeSlot]:
        """Generates deterministic free interview slots over the upcoming business days."""
        slots: list[TimeSlot] = []
        now = datetime.now(UTC)
        held_slot_ids = set(self.state.get("holds", {}).keys())

        # Seed standard meeting hours (e.g. 14:00, 15:30, 17:00 UTC) across next business days
        candidate_hours = [(14, 0), (15, 30), (17, 0), (19, 0)]

        day_count = 0
        current_offset = 1
        while day_count < days_ahead and current_offset <= 20:
            target_date = now + timedelta(days=current_offset)
            current_offset += 1
            # Skip Saturday (5) and Sunday (6)
            if target_date.weekday() >= 5:
                continue

            day_count += 1
            for hr, mn in candidate_hours:
                start_dt = target_date.replace(hour=hr, minute=mn, second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=duration_min)
                slot_id = f"slot_{start_dt.strftime('%Y%m%d_%H%M')}"

                # Skip if already tentatively held
                if slot_id in held_slot_ids:
                    continue

                formatted_day = start_dt.strftime("%A, %b %d")
                formatted_time = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')} UTC"
                formatted_str = f"{formatted_day} at {formatted_time}"

                slots.append(
                    TimeSlot(
                        slot_id=slot_id,
                        start_time=start_dt.isoformat(),
                        end_time=end_dt.isoformat(),
                        duration_min=duration_min,
                        formatted=formatted_str,
                    )
                )

        return slots

    def create_tentative_hold(
        self,
        slot_id: str,
        title: str,
        idempotency_key: str = "",
    ) -> TentativeHoldOutput:
        """Registers a tentative calendar hold for an interview slot."""
        if idempotency_key:
            cached = self.check_idempotency(idempotency_key, "create_tentative_hold")
            if cached:
                return TentativeHoldOutput(**cached)

        # Parse slot timestamp
        now_iso = datetime.now(UTC).isoformat()
        hold_id = f"hold_{uuid4().hex[:10]}"

        # Compute times from slot_id or default offsets
        try:
            date_str = slot_id.replace("slot_", "")
            slot_dt = datetime.strptime(date_str, "%Y%m%d_%H%M").replace(tzinfo=UTC)
            start_iso = slot_dt.isoformat()
            end_iso = (slot_dt + timedelta(minutes=30)).isoformat()
        except Exception:  # noqa: BLE001
            start_iso = now_iso
            end_iso = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()

        record = {
            "hold_id": hold_id,
            "slot_id": slot_id,
            "title": title,
            "start_time": start_iso,
            "end_time": end_iso,
            "status": "tentative",
            "held_at": now_iso,
            "idempotency_key": idempotency_key or None,
        }

        self.state.setdefault("holds", {})[slot_id] = record
        self._save_state()

        if idempotency_key:
            self.store_idempotency(idempotency_key, "create_tentative_hold", record)

        return TentativeHoldOutput(**record)

    def create_email_draft(
        self,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str = "",
    ) -> EmailDraftOutput:
        """Saves a draft client email message to local mock store."""
        if idempotency_key:
            cached = self.check_idempotency(idempotency_key, "create_email_draft")
            if cached:
                return EmailDraftOutput(**cached)

        draft_id = f"draft_{uuid4().hex[:10]}"
        now_iso = datetime.now(UTC).isoformat()

        record = {
            "draft_id": draft_id,
            "to": to,
            "subject": subject,
            "body": body,
            "status": "draft",
            "created_at": now_iso,
            "idempotency_key": idempotency_key or None,
        }

        self.state.setdefault("drafts", {})[draft_id] = record
        self._save_state()

        if idempotency_key:
            self.store_idempotency(idempotency_key, "create_email_draft", record)

        return EmailDraftOutput(**record)
