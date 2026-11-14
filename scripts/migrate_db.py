"""Database migration CLI script (AI-4016 Prompt 9 Part 0).

Creates application tables (audit_trace, dead_letter, proposal_submissions)
and configures LangGraph Postgres checkpointer and store schemas.
"""
from __future__ import annotations

import argparse
import sys

from agent.db import get_db_url, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GigBid database migrations and schema setup.")
    parser.add_argument("--url", default=None, help="Postgres database URL override.")
    args = parser.parse_args()

    target_url = args.url or get_db_url()
    print(f"[migrate_db] Connecting to {target_url}...")

    success = init_db(target_url)
    if success:
        print("[migrate_db] Migrations and LangGraph schemas applied successfully.")
        sys.exit(0)
    else:
        print("[migrate_db] ERROR: Failed applying database migrations.")
        sys.exit(1)


if __name__ == "__main__":
    main()
