"""Lightweight PII masking helper for audit logging and marketplace telemetry."""
from __future__ import annotations

import re
from typing import Any

# Regex patterns kept concise and under 300 characters to comply with repo rules.
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
CRYPTO_RE = re.compile(r"\b(?:0x[a-fA-F0-9]{40}|(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59})\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")


def mask_pii(text: str) -> str:
    """Replaces emails, phones, payment strings with redaction tokens."""
    if not isinstance(text, str) or not text:
        return text

    masked = EMAIL_RE.sub("[EMAIL_MASKED]", text)
    masked = CARD_RE.sub("[PAYMENT_MASKED]", masked)
    masked = CRYPTO_RE.sub("[PAYMENT_MASKED]", masked)
    masked = IBAN_RE.sub("[PAYMENT_MASKED]", masked)
    return PHONE_RE.sub("[PHONE_MASKED]", masked)


def mask_pii_obj(obj: Any) -> Any:
    """Recursively traverses objects (dicts, lists) and masks PII in string values."""
    if isinstance(obj, str):
        return mask_pii(obj)
    elif isinstance(obj, dict):
        return {k: mask_pii_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [mask_pii_obj(elem) for elem in obj]
    elif isinstance(obj, tuple):
        return tuple(mask_pii_obj(elem) for elem in obj)
    return obj
