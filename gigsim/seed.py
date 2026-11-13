"""Database Initialization and Seeding for GigSim SQLite (AI-4016 GigBid Phase 1b Part 3).

Stores marketplace state in a local SQLite database under gigsim/state/gigsim.db.
Supports atomic resets, idempotent operations, and fast offline state progression.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "state" / "gigsim.db"
SEED_DIR = Path(__file__).resolve().parent / "seed"
REPO_ROOT = Path(__file__).resolve().parent.parent


def get_db_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if isinstance(db_path, str) and db_path != ":memory:":
        db_path = Path(db_path)
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Creates database tables if they do not exist."""
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            industry TEXT NOT NULL,
            country TEXT NOT NULL,
            payment_verified INTEGER NOT NULL,
            total_spent REAL NOT NULL,
            hire_rate REAL NOT NULL,
            avg_rating REAL NOT NULL,
            jobs_posted INTEGER NOT NULL,
            review_count INTEGER NOT NULL,
            hidden_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            budget_type TEXT NOT NULL,
            budget_min REAL NOT NULL,
            budget_max REAL NOT NULL,
            client_country TEXT NOT NULL,
            client_id TEXT NOT NULL,
            posted_at TEXT NOT NULL,
            connects_cost INTEGER NOT NULL,
            synthetic INTEGER NOT NULL,
            is_released INTEGER NOT NULL DEFAULT 0,
            released_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            cover_letter TEXT NOT NULL,
            screening_answers_json TEXT,
            bid_amount REAL NOT NULL,
            connects_cost INTEGER NOT NULL,
            status TEXT NOT NULL, -- draft, submitted, viewed, replied, interview, hired, rejected
            created_at TEXT NOT NULL,
            submitted_at TEXT,
            idempotency_key TEXT,
            score REAL DEFAULT 0.0,
            client_feedback TEXT
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender TEXT NOT NULL, -- freelancer or client
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            idempotency_key TEXT
        );

        CREATE TABLE IF NOT EXISTS idempotency_cache (
            key TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            response_json TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def seed_database(
    conn: sqlite3.Connection,
    clients_file: Path | None = None,
    stream_jobs_file: Path | None = None,
    rules_file: Path | None = None,
    initial_release_count: int = 15
) -> None:
    """Populates database with initial seed data."""
    if clients_file is None:
        clients_file = SEED_DIR / "clients.json"
    if stream_jobs_file is None:
        stream_jobs_file = REPO_ROOT / "data" / "processed" / "jobs_stream.jsonl"
    if rules_file is None:
        rules_file = SEED_DIR / "platform_rules.yaml"

    init_schema(conn)

    # 1. Platform rules & Meta config
    rules: dict[str, Any] = {}
    if rules_file.exists():
        rules = yaml.safe_load(rules_file.read_text(encoding="utf-8")) or {}

    connects_cfg = rules.get("connects", {})
    initial_balance = connects_cfg.get("initial_balance", 150)
    weekly_grant = connects_cfg.get("weekly_grant", 80)
    start_time = "2024-08-01T12:00:00Z"

    with conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('simulated_time', ?)", (start_time,))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('connects_balance', ?)", (str(initial_balance),))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('weekly_grant', ?)", (str(weekly_grant),))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_grant_date', ?)", (start_time,))

    # 2. Clients
    if clients_file.exists():
        clients_raw = json.loads(clients_file.read_text(encoding="utf-8"))
        with conn:
            for c in clients_raw:
                pub = c["public"]
                hidden = c["hidden"]
                conn.execute("""
                INSERT OR REPLACE INTO clients (
                    id, company, industry, country, payment_verified, total_spent,
                    hire_rate, avg_rating, jobs_posted, review_count, hidden_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pub["id"], pub["company"], pub["industry"], pub["country"],
                    1 if pub["payment_verified"] else 0, pub["total_spent"],
                    pub["hire_rate"], pub["avg_rating"], pub["jobs_posted"],
                    pub["review_count"], json.dumps(hidden)
                ))

    # 3. Stream Jobs
    if stream_jobs_file.exists():
        lines = stream_jobs_file.read_text(encoding="utf-8").strip().splitlines()
        jobs = [json.loads(l) for l in lines]
        with conn:
            for idx, j in enumerate(jobs):
                # Release the first `initial_release_count` jobs right away
                is_rel = 1 if idx < initial_release_count else 0
                conn.execute("""
                INSERT OR REPLACE INTO jobs (
                    id, title, description, category, skills_json, budget_type,
                    budget_min, budget_max, client_country, client_id, posted_at,
                    connects_cost, synthetic, is_released, released_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    j["id"], j["title"], j["description"], j["category"],
                    json.dumps(j["skills"]), j["budget_type"], j["budget_min"],
                    j["budget_max"], j["client_country"], j["client_id"], j["posted_at"],
                    j["connects_cost"], 1 if j.get("synthetic", True) else 0, is_rel, idx + 1
                ))

    print(f"[seed] Initialized database with {initial_balance} connects and {initial_release_count} released jobs.")


def reset_database(
    conn: sqlite3.Connection,
    clients_file: Path | None = None,
    stream_jobs_file: Path | None = None,
    rules_file: Path | None = None
) -> None:
    """Cleans all dynamic runtime tables and resets state to fresh seed."""
    init_schema(conn)
    with conn:
        conn.execute("DELETE FROM proposals")
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM idempotency_cache")
        conn.execute("UPDATE jobs SET is_released = 0 WHERE released_order > 15")
        conn.execute("UPDATE jobs SET is_released = 1 WHERE released_order <= 15")

    seed_database(
        conn=conn,
        clients_file=clients_file,
        stream_jobs_file=stream_jobs_file,
        rules_file=rules_file,
        initial_release_count=15
    )


if __name__ == "__main__":
    db = get_db_connection()
    seed_database(db)
