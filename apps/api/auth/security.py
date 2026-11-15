"""Security primitives: bcrypt hashing, JWT issuance/verification, Fernet token encryption."""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

DEFAULT_SECRET_KEY = "gigbid_super_secret_development_jwt_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def get_jwt_secret() -> str:
    return os.getenv("APP_SECRET_KEY", DEFAULT_SECRET_KEY)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Encodes a JWT payload with expiration."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token; returns None on failure."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def _get_fernet() -> Fernet:
    """Constructs a Fernet cipher from TOKEN_ENCRYPTION_KEY env var."""
    raw = os.getenv("TOKEN_ENCRYPTION_KEY", "default_fernet_secret_key_for_gigbid_env_test=")
    try:
        return Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except (ValueError, TypeError):
        # Generate 32 url-safe base64 bytes deterministically
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)


def encrypt_token(raw_token: str) -> str:
    """Encrypts sensitive external API tokens at rest using Fernet."""
    if not raw_token:
        return ""
    cipher = _get_fernet()
    return cipher.encrypt(raw_token.encode("utf-8")).decode("utf-8")


def decrypt_token(cipher_text: str) -> str:
    """Decrypts ciphertext into the raw plaintext token."""
    if not cipher_text:
        return ""
    cipher = _get_fernet()
    return cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
