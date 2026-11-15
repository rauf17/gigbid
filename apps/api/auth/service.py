"""User authentication, profile management, and credential repository service."""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

import psycopg

from agent.db import (
    _MEMORY_USER_CONNECTIONS,
    _MEMORY_USER_PROFILES,
    _MEMORY_USERS,
    get_db_url,
)
from apps.api.auth.security import decrypt_token, encrypt_token, hash_password

logger = logging.getLogger(__name__)


def _is_db_available() -> bool:
    try:
        url = get_db_url()
        with psycopg.connect(url, connect_timeout=1):
            return True
    except (psycopg.Error, OSError):
        return False


def get_user_by_email(email: str) -> dict[str, Any] | None:
    norm_email = email.strip().lower()
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, persona_id, created_at FROM users WHERE lower(email) = %s",
                (norm_email,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "password_hash": row[2],
                    "persona_id": row[3],
                    "created_at": str(row[4]) if row[4] else None,
                }
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres unavailable, checking memory: %s", exc)

    # In-memory fallback
    for u in _MEMORY_USERS.values():
        if u["email"].lower() == norm_email:
            return u
    return None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, persona_id, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "password_hash": row[2],
                    "persona_id": row[3],
                    "created_at": str(row[4]) if row[4] else None,
                }
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres unavailable, checking memory: %s", exc)

    return _MEMORY_USERS.get(user_id)


def create_user(
    email: str,
    password_hash: str,
    persona_id: str = "ai_ml",
    user_id: str | None = None,
) -> dict[str, Any]:
    norm_email = email.strip().lower()
    uid = user_id or f"usr_{uuid4().hex[:12]}"
    user_record = {
        "id": uid,
        "email": norm_email,
        "password_hash": password_hash,
        "persona_id": persona_id,
        "created_at": None,
    }

    try:
        url = get_db_url()
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, email, password_hash, persona_id) VALUES (%s, %s, %s, %s) "
                "RETURNING created_at",
                (uid, norm_email, password_hash, persona_id),
            )
            row = cur.fetchone()
            if row and row[0]:
                user_record["created_at"] = str(row[0])
            # Initialize default user profile
            cur.execute(
                "INSERT INTO user_profiles (user_id, persona_id) VALUES (%s, %s) "
                "ON CONFLICT (user_id) DO NOTHING",
                (uid, persona_id),
            )
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres insert failed, saving to memory: %s", exc)

    _MEMORY_USERS[uid] = user_record
    if uid not in _MEMORY_USER_PROFILES:
        _MEMORY_USER_PROFILES[uid] = {
            "user_id": uid,
            "persona_id": persona_id,
            "hourly_rate": 50.0,
            "floor_rate": 30.0,
            "filters": {},
            "weekly_connects_budget": 40,
            "autonomy_level": "semi_autonomous",
            "saved_searches": [],
        }
    return user_record


def seed_reviewer_user() -> dict[str, Any] | None:
    """Seeds the REVIEWER user on application startup from environment variables."""
    reviewer_email = os.getenv("REVIEWER_EMAIL", "reviewer@gigbid.local")
    reviewer_password = os.getenv("REVIEWER_PASSWORD", "replace_me_reviewer_password")
    if not reviewer_email or not reviewer_password:
        return None

    existing = get_user_by_email(reviewer_email)
    if existing:
        return existing

    pw_hash = hash_password(reviewer_password)
    user = create_user(
        email=reviewer_email,
        password_hash=pw_hash,
        persona_id="ai_ml",
        user_id="usr_reviewer",
    )
    logger.info("[auth.service] Seeded reviewer user: %s (persona: ai_ml)", reviewer_email)
    return user


def get_user_profile(user_id: str) -> dict[str, Any]:
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, persona_id, hourly_rate, floor_rate, filters, weekly_connects_budget, "
                "autonomy_level, saved_searches FROM user_profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "persona_id": row[1],
                    "hourly_rate": float(row[2]) if row[2] is not None else 50.0,
                    "floor_rate": float(row[3]) if row[3] is not None else 30.0,
                    "filters": row[4] if isinstance(row[4], dict) else {},
                    "weekly_connects_budget": int(row[5]) if row[5] is not None else 40,
                    "autonomy_level": row[6] or "semi_autonomous",
                    "saved_searches": row[7] if isinstance(row[7], list) else [],
                }
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres read profile failed, using memory: %s", exc)

    if user_id in _MEMORY_USER_PROFILES:
        return _MEMORY_USER_PROFILES[user_id]

    default_profile = {
        "user_id": user_id,
        "persona_id": "ai_ml",
        "hourly_rate": 50.0,
        "floor_rate": 30.0,
        "filters": {},
        "weekly_connects_budget": 40,
        "autonomy_level": "semi_autonomous",
        "saved_searches": [],
    }
    _MEMORY_USER_PROFILES[user_id] = default_profile
    return default_profile


def update_user_profile(user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_user_profile(user_id)
    for k, v in updates.items():
        if v is not None:
            current[k] = v

    try:
        url = get_db_url()
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_profiles (user_id, persona_id, hourly_rate, floor_rate, filters, "
                "weekly_connects_budget, autonomy_level, saved_searches, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "persona_id = EXCLUDED.persona_id, hourly_rate = EXCLUDED.hourly_rate, "
                "floor_rate = EXCLUDED.floor_rate, filters = EXCLUDED.filters, "
                "weekly_connects_budget = EXCLUDED.weekly_connects_budget, "
                "autonomy_level = EXCLUDED.autonomy_level, saved_searches = EXCLUDED.saved_searches, "
                "updated_at = NOW()",
                (
                    user_id,
                    current["persona_id"],
                    current["hourly_rate"],
                    current["floor_rate"],
                    json.dumps(current["filters"]),
                    current["weekly_connects_budget"],
                    current["autonomy_level"],
                    json.dumps(current["saved_searches"]),
                ),
            )
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres update profile failed: %s", exc)

    _MEMORY_USER_PROFILES[user_id] = current
    return current


def store_marketplace_token(user_id: str, raw_token: str) -> None:
    """Stores the encrypted marketplace token. Never logs or returns plaintext."""
    encrypted = encrypt_token(raw_token)
    try:
        url = get_db_url()
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_connections (user_id, encrypted_marketplace_token, updated_at) "
                "VALUES (%s, %s, NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "encrypted_marketplace_token = EXCLUDED.encrypted_marketplace_token, updated_at = NOW()",
                (user_id, encrypted),
            )
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres store token failed: %s", exc)

    _MEMORY_USER_CONNECTIONS[user_id] = encrypted


def get_marketplace_token(user_id: str) -> str | None:
    """Retrieves and decrypts the user's marketplace token for internal port use."""
    encrypted = None
    try:
        url = get_db_url()
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT encrypted_marketplace_token FROM user_connections WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                encrypted = row[0]
    except (psycopg.Error, OSError) as exc:
        logger.debug("[auth.service] Postgres read token failed: %s", exc)

    if not encrypted:
        encrypted = _MEMORY_USER_CONNECTIONS.get(user_id)

    if encrypted:
        return decrypt_token(encrypted)
    return None
