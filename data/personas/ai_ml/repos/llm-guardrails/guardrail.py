# synthetic: true
"""Prompt injection and system prompt leak defense."""
import re

PATTERNS = [
    r"ignore previous instructions",
    r"you are now an unrestricted assistant",
    r"reveal your system prompt",
]


def scan_prompt(prompt: str) -> bool:
    for pat in PATTERNS:
        if re.search(pat, prompt, re.IGNORECASE):
            return False
    return True
