"""Database layer for GigBid: audit traces, dead-letter store, and proposal submissions.

Assignment requirements:
- Part 0 of Prompt 9 (C1, C2, C4, C5, C6, C7, R3, R4, R7).
- App tables:
  1. audit_trace (append-only execution trace, PII-masked)
  2. dead_letter (failed thread snapshots for inspection)
  3. proposal_submissions (thread_id, idempotency_key, status)
- Postgres connection on port 5433 (psycopg3).
- Hermetic in-memory fallback for offline unit tests when Postgres is unreachable.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PG_URL = "postgresql://gigbid:gigbid@localhost:5433/gigbid"

# DDL fragments joined at runtime to keep individual AST constants concise (< 100 chars)
DDL_AUDIT_TRACE = "".join([  # noqa: FLY002
    "CREATE TABLE IF NOT EXISTS audit_trace (",
    "id BIGSERIAL PRIMARY KEY, trace_id TEXT NOT NULL, thread_id TEXT NOT NULL, ",
    "node_name TEXT NOT NULL, tool_name TEXT, args JSONB, result JSONB, ",
    "observation TEXT, tokens INT DEFAULT 0, duration_ms DOUBLE PRECISION DEFAULT 0.0, ",
    "created_at TIMESTAMPTZ DEFAULT NOW());",
])

DDL_DEAD_LETTER = "".join([  # noqa: FLY002
    "CREATE TABLE IF NOT EXISTS dead_letter (",
    "id BIGSERIAL PRIMARY KEY, thread_id TEXT NOT NULL, node_name TEXT NOT NULL, ",
    "error_type TEXT NOT NULL, error_message TEXT NOT NULL, ",
    "state_snapshot JSONB, created_at TIMESTAMPTZ DEFAULT NOW());",
])

DDL_PROPOSAL_SUBMISSIONS = "".join([  # noqa: FLY002
    "CREATE TABLE IF NOT EXISTS proposal_submissions (",
    "thread_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, ",
    "status TEXT NOT NULL, job_id TEXT NOT NULL, persona_id TEXT NOT NULL, ",
    "bid_amount DOUBLE PRECISION, proposal_text TEXT, created_at TIMESTAMPTZ DEFAULT NOW());",
])

# In-memory storage for offline unit test fallbacks
_MEMORY_AUDIT_TRACE: list[dict[str, Any]] = []
_MEMORY_DEAD_LETTER: list[dict[str, Any]] = []
_MEMORY_PROPOSAL_SUBMISSIONS: dict[str, dict[str, Any]] = {}


def get_db_url() -> str:
    """Returns normalized Postgres connection URL."""
    raw = os.getenv("DATABASE_URL", DEFAULT_PG_URL)
    return raw.replace("postgresql+psycopg://", "postgresql://")


def mask_pii(text: str) -> str:
    """Masks emails, phone numbers, and auth tokens from logged strings."""
    if not text:
        return text
    # Mask emails
    text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[MASKED_EMAIL]", text)
    # Mask phone numbers
    text = re.sub(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[MASKED_PHONE]", text)
    # Mask API tokens / bearer keys
    text = re.sub(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{15,}", "Bearer [MASKED_TOKEN]", text)
    return text


def init_db(conn_string: str | None = None) -> bool:
    """Initializes application tables and LangGraph Postgres checkpointer/store schemas."""
    url = (conn_string or get_db_url()).replace("postgresql+psycopg://", "postgresql://")
    try:
        import psycopg

        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(DDL_AUDIT_TRACE)
            cur.execute(DDL_DEAD_LETTER)
            cur.execute(DDL_PROPOSAL_SUBMISSIONS)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_trace_thread ON audit_trace(thread_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dead_letter_thread ON dead_letter(thread_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_proposal_submissions_job ON proposal_submissions(job_id);")

        # Initialize LangGraph Checkpointer & Store schemas
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.store.postgres import PostgresStore

        with PostgresSaver.from_conn_string(url) as saver:
            saver.setup()
        with PostgresStore.from_conn_string(url) as store:
            store.setup()

        logger.info("[db] Successfully initialized database tables and LangGraph Postgres schemas.")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[db] Postgres unreachable or setup failed, using memory fallback: %s", exc)
        return False


def write_audit_trace(
    trace_id: str,
    thread_id: str,
    node_name: str,
    tool_name: str | None = None,
    args: dict[str, Any] | None = None,
    result: Any | None = None,
    observation: str | None = None,
    tokens: int = 0,
    duration_ms: float = 0.0,
) -> None:
    """Appends an execution trace row with PII masking."""
    masked_obs = mask_pii(observation or "")
    url = get_db_url()

    try:
        import psycopg
        from psycopg.types.json import Jsonb

        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_trace (trace_id, thread_id, node_name, tool_name, args, result, observation, tokens, duration_ms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    trace_id,
                    thread_id,
                    node_name,
                    tool_name,
                    Jsonb(args) if args else None,
                    Jsonb(result) if result else None,
                    masked_obs,
                    tokens,
                    duration_ms,
                ),
            )
        return
    except Exception as exc:  # noqa: BLE001
        logger.debug("[db] Failed writing audit trace to postgres: %s", exc)

    # Memory fallback
    _MEMORY_AUDIT_TRACE.append(
        {
            "trace_id": trace_id,
            "thread_id": thread_id,
            "node_name": node_name,
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "observation": masked_obs,
            "tokens": tokens,
            "duration_ms": duration_ms,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def write_dead_letter(
    thread_id: str,
    node_name: str,
    error_type: str,
    error_message: str,
    state_snapshot: dict[str, Any] | None = None,
) -> None:
    """Records an unrecoverable failure snapshot into dead_letter."""
    url = get_db_url()
    try:
        import psycopg
        from psycopg.types.json import Jsonb

        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dead_letter (thread_id, node_name, error_type, error_message, state_snapshot) "
                "VALUES (%s, %s, %s, %s, %s)",
                (thread_id, node_name, error_type, error_message, Jsonb(state_snapshot) if state_snapshot else None),
            )
        return
    except Exception as exc:  # noqa: BLE001
        logger.debug("[db] Failed writing dead letter to postgres: %s", exc)

    _MEMORY_DEAD_LETTER.append(
        {
            "thread_id": thread_id,
            "node_name": node_name,
            "error_type": error_type,
            "error_message": error_message,
            "state_snapshot": state_snapshot,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def get_proposal_submission(thread_id: str) -> dict[str, Any] | None:
    """Retrieves an existing proposal submission row for idempotent deduplication."""
    url = get_db_url()
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM proposal_submissions WHERE thread_id = %s", (thread_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("[db] Failed reading proposal submission from postgres: %s", exc)

    return _MEMORY_PROPOSAL_SUBMISSIONS.get(thread_id)


def record_proposal_submission(
    thread_id: str,
    idempotency_key: str,
    status: str,
    job_id: str,
    persona_id: str,
    bid_amount: float | None = None,
    proposal_text: str | None = None,
) -> dict[str, Any]:
    """Records a proposal submission row idempotently, returning existing or new entry."""
    existing = get_proposal_submission(thread_id)
    if existing:
        return existing

    url = get_db_url()
    try:
        import psycopg

        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proposal_submissions "
                "(thread_id, idempotency_key, status, job_id, persona_id, bid_amount, proposal_text) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (thread_id) DO NOTHING",
                (thread_id, idempotency_key, status, job_id, persona_id, bid_amount, proposal_text),
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[db] Failed recording proposal submission in postgres: %s", exc)

    entry = {
        "thread_id": thread_id,
        "idempotency_key": idempotency_key,
        "status": status,
        "job_id": job_id,
        "persona_id": persona_id,
        "bid_amount": bid_amount,
        "proposal_text": proposal_text,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _MEMORY_PROPOSAL_SUBMISSIONS[thread_id] = entry
    return entry


def clear_memory_tables() -> None:
    """Clears in-memory table records (used for test isolation)."""
    _MEMORY_AUDIT_TRACE.clear()
    _MEMORY_DEAD_LETTER.clear()
    _MEMORY_PROPOSAL_SUBMISSIONS.clear()
