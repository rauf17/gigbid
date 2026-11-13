# synthetic: true
"""Structured output JSON schema validator."""
import json


def validate_json_output(raw_str: str, required_keys: list[str]) -> bool:
    try:
        data = json.loads(raw_str)
        return all(k in data for k in required_keys)
    except (json.JSONDecodeError, TypeError):
        return False
