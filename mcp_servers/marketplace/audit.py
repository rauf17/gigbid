"""Append-only audit store and idempotency cache for Marketplace MCP server.

Enforces:
- Zero UPDATE or DELETE paths in SQL (pure append-only log).
- Automatic PII redaction of emails, phones, and payment data before disk writes.
- Keyed local cache for idempotent write tools.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.pii import mask_pii_obj

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "state" / "audit.db"


class AuditStore:
    """Thread-safe, append-only SQLite store for tool invocations and idempotency."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
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

    def record_audit(
        self,
        user_id: str,
        tool: str,
        arguments: dict[str, Any],
        result: Any,
        status: str,
        trace_id: str,
    ) -> None:
        """Appends an execution record to the audit log after PII masking.

        No UPDATE or DELETE is ever executed.
        """
        now_iso = datetime.now(UTC).isoformat()
        clean_args = mask_pii_obj(arguments)
        clean_res = mask_pii_obj(result)

        args_json = json.dumps(clean_args, default=str)
        res_json = json.dumps(clean_res, default=str)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (ts, user_id, tool, arguments_json, result_json, status, trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso, user_id, tool, args_json, res_json, status, trace_id),
            )

    def get_cached_idempotent_result(self, key: str, tool: str) -> dict[str, Any] | None:
        """Retrieves previously cached result for an idempotency key and tool."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT result_json FROM idempotency_cache WHERE key = ? AND tool = ?",
                (key, tool),
            ).fetchone()
            if row:
                try:
                    return json.loads(row["result_json"])
                except (json.JSONDecodeError, ValueError):
                    return None
        return None

    def store_idempotent_result(self, key: str, tool: str, result: dict[str, Any]) -> None:
        """Stores a write result keyed by idempotency key.

        Uses INSERT OR IGNORE to guarantee immutability (never overwrites or updates).
        """
        now_iso = datetime.now(UTC).isoformat()
        res_json = json.dumps(result, default=str)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO idempotency_cache (key, tool, result_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, tool, res_json, now_iso),
            )

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Queries recent audit entries for testing and compliance inspection."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT ts, user_id, tool, arguments_json, result_json, status, trace_id FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
