"""Unit tests for PII masking helper (agent/pii.py)."""
from agent.pii import mask_pii, mask_pii_obj


def test_mask_emails() -> None:
    text = "Contact me at alice@example.com or bob.work+test@sub.domain.co.uk please."
    masked = mask_pii(text)
    assert "alice@example.com" not in masked
    assert "bob.work+test@sub.domain.co.uk" not in masked
    assert "[EMAIL_MASKED]" in masked


def test_mask_phone_numbers() -> None:
    text = "Call +1-555-123-4567 or (800) 555-0199 for off-platform discussion."
    masked = mask_pii(text)
    assert "+1-555-123-4567" not in masked
    assert "(800) 555-0199" not in masked
    assert "[PHONE_MASKED]" in masked


def test_mask_payment_and_crypto() -> None:
    cc = "Credit card: 4111 2222 3333 4444 or 5500-0000-0000-0004"
    masked_cc = mask_pii(cc)
    assert "4111 2222 3333 4444" not in masked_cc
    assert "[PAYMENT_MASKED]" in masked_cc

    crypto = "Pay via USDT to 0x71C7656EC7ab88b098defB751B7401B5f6d8976F or 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    masked_crypto = mask_pii(crypto)
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" not in masked_crypto
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" not in masked_crypto
    assert "[PAYMENT_MASKED]" in masked_crypto


def test_mask_pii_obj_nested() -> None:
    nested = {
        "job_id": "job_01",
        "client": {
            "contact": "alice@gmail.com",
            "phone": "555-234-5678",
        },
        "bids": [
            {"note": "Send deposit to 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"},
            {"note": "clean bid without pii"},
        ],
    }
    cleaned = mask_pii_obj(nested)
    assert cleaned["job_id"] == "job_01"
    assert cleaned["client"]["contact"] == "[EMAIL_MASKED]"
    assert cleaned["client"]["phone"] == "[PHONE_MASKED]"
    assert cleaned["bids"][0]["note"] == "Send deposit to [PAYMENT_MASKED]"
    assert cleaned["bids"][1]["note"] == "clean bid without pii"
